//! Deterministic repository persistence for LLMLang Semantic Program Graph tables.

mod graph;
pub use graph::*;
mod record;

pub use record::content_hash;
use record::{digest, TableRecord as Record};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
use std::fs::{self, File};
use std::io::{BufReader, BufWriter, Read, Seek, SeekFrom, Write};
use std::path::Path;
use tempfile::{tempdir_in, NamedTempFile, TempDir};

pub const TABLES: [&str; 12] = [
    "bindings",
    "contract_rules",
    "contracts",
    "functions",
    "interfaces",
    "structure_bindings",
    "structure_layouts",
    "structure_types",
    "structures",
    "verification_obligations",
    "verification_runs",
    "versions",
];

const PROFILE: &str = "llmlang.spg.tables.v3";
const MANIFEST: &str = "manifest.json";
const MAGIC: &[u8; 8] = b"LLSPG\x03\r\n";
const HEADER: u64 = 40;
const MAX_RECORD: usize = 1 << 20;
const MAX_COMPRESSED: usize = MAX_RECORD + MAX_RECORD / 255 + 16;
const MAX_METADATA: usize = 16 << 20;

pub type Rows = BTreeMap<String, Value>;
pub type Tables = BTreeMap<String, Rows>;
pub type Index = BTreeMap<String, u64>;
pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("{0}")]
    Invalid(String),
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
    #[error("unreadable Protobuf record: {0}")]
    Protobuf(prost::DecodeError),
}

fn invalid(message: impl Into<String>) -> Error {
    Error::Invalid(message.into())
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    pub language_version: String,
    /// Dependency name to exact package identity as interpreted by the caller.
    #[serde(default)]
    pub dependencies: BTreeMap<String, String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Package {
    pub manifest: Manifest,
    pub tables: Tables,
}

impl Package {
    pub fn empty(manifest: Manifest) -> Self {
        Self {
            manifest,
            tables: TABLES
                .into_iter()
                .map(|table| (table.into(), Rows::new()))
                .collect(),
        }
    }
}

#[derive(Debug, Default, Clone, Copy)]
pub struct SaveOptions {
    pub write_text_dump: bool,
}

#[derive(Debug, Default, Clone, Copy)]
pub struct LoadOptions<'a> {
    pub write_text_dump: bool,
    /// A new directory outside the input package.
    pub text_dump_dir: Option<&'a Path>,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PackageManifest {
    profile: String,
    language_version: String,
    #[serde(default)]
    dependencies: BTreeMap<String, String>,
}

fn check_manifest(manifest: &Manifest, supported_versions: &[&str]) -> Result<()> {
    semver::Version::parse(&manifest.language_version)
        .map_err(|_| invalid("invalid manifest language_version"))?;
    if !supported_versions.contains(&manifest.language_version.as_str()) {
        return Err(invalid(format!(
            "unsupported language_version {}",
            manifest.language_version
        )));
    }
    Ok(())
}

fn read_manifest(path: &Path, supported_versions: &[&str]) -> Result<Manifest> {
    let manifest: PackageManifest = serde_json::from_slice(&read_metadata(&path.join(MANIFEST))?)?;
    if manifest.profile != PROFILE {
        return Err(invalid("unsupported repository profile"));
    }
    let result = Manifest {
        language_version: manifest.language_version,
        dependencies: manifest.dependencies,
    };
    check_manifest(&result, supported_versions)?;
    Ok(result)
}

/// Write a complete package and publish it at a new directory.
pub fn save(path: &Path, package: &Package, options: SaveOptions) -> Result<()> {
    check_manifest(&package.manifest, &[&package.manifest.language_version])?;
    if !package.tables.keys().map(String::as_str).eq(TABLES) {
        return Err(invalid(
            "package must contain exactly the repository profile tables",
        ));
    }
    let staging = stage(path)?;
    let manifest = PackageManifest {
        profile: PROFILE.into(),
        language_version: package.manifest.language_version.clone(),
        dependencies: package.manifest.dependencies.clone(),
    };
    write_json(File::create(staging.path().join(MANIFEST))?, &manifest)?;
    for (table, rows) in &package.tables {
        let mut dump = BufWriter::new(File::create(dump_path(staging.path(), table))?);
        dump.write_all(MAGIC)?;
        let mut index = Index::new();
        let mut offset = MAGIC.len() as u64;
        let mut text = TextDump::open(staging.path(), table, options.write_text_dump)?;
        for (key, row) in rows {
            let record = Record::new(table, key, row)?;
            let raw = record.encode_to_vec();
            if raw.len() > MAX_RECORD {
                return Err(invalid("record exceeds byte limit"));
            }
            let compressed =
                lz4::block::compress(&raw, Some(lz4::block::CompressionMode::FAST(1)), false)?;
            let hash = digest(key, row)?;
            insert_hash(&mut index, &hash, offset)?;
            dump.write_all(&(compressed.len() as u32).to_le_bytes())?;
            dump.write_all(&(raw.len() as u32).to_le_bytes())?;
            dump.write_all(&hash)?;
            dump.write_all(&compressed)?;
            offset += HEADER + compressed.len() as u64;
            text.record(&record)?;
        }
        dump.flush()?;
        text.finish()?;
        write_index(staging.path(), table, &index)?;
    }
    publish(staging, path)
}

/// Read all records and verify that every index describes its companion dump.
pub fn load(path: &Path, supported_versions: &[&str], options: LoadOptions<'_>) -> Result<Package> {
    let manifest = read_manifest(path, supported_versions)?;
    let text = if options.write_text_dump {
        let destination = options
            .text_dump_dir
            .ok_or_else(|| invalid("missing text dump directory"))?;
        let parent = fs::canonicalize(parent(destination))?;
        if parent.starts_with(fs::canonicalize(path)?) {
            return Err(invalid(
                "text dump directory must be outside the input package",
            ));
        }
        Some((stage(destination)?, destination))
    } else {
        None
    };
    let mut tables = Tables::new();
    for table in TABLES {
        let expected = read_index(path, table)?;
        let mut rows = Rows::new();
        let mut output = TextDump::open(
            text.as_ref().map_or(path, |(stage, _)| stage.path()),
            table,
            text.is_some(),
        )?;
        let observed = scan(path, table, |frame| {
            output.record(&frame.record)?;
            rows.insert(frame.key, frame.row);
            Ok(())
        })?;
        if expected != observed {
            return Err(invalid(format!("{table}: index does not describe dump")));
        }
        output.finish()?;
        tables.insert(table.into(), rows);
    }
    if let Some((staging, destination)) = text {
        publish(staging, destination)?;
    }
    Ok(Package { manifest, tables })
}

/// Rebuild a table index from a fully verified dump and replace it atomically.
pub fn rebuild_index(path: &Path, supported_versions: &[&str], table: &str) -> Result<Index> {
    read_manifest(path, supported_versions)?;
    check_table(table)?;
    let index = scan(path, table, |_| Ok(()))?;
    write_index(path, table, &index)?;
    Ok(index)
}

/// Read a record by Content Hash without decoding preceding records.
/// The cache, when supplied, provides candidates which are verified before use.
pub fn load_record(
    path: &Path,
    supported_versions: &[&str],
    table: &str,
    hash: &str,
    cache: Option<&BTreeMap<String, (String, Value)>>,
) -> Result<Option<(String, Value)>> {
    read_manifest(path, supported_versions)?;
    check_table(table)?;
    check_hash(hash)?;
    let index = read_index(path, table)?;
    let Some(&offset) = index.get(hash) else {
        return Ok(None);
    };
    if let Some((key, row)) = cache.and_then(|cache| cache.get(hash)) {
        let size = Record::new(table, key, row)?.encode_to_vec().len();
        if size > MAX_RECORD || hex::encode(digest(key, row)?) != hash {
            return Err(invalid(
                "cached record content hash mismatch or invalid size",
            ));
        }
        return Ok(Some((key.clone(), row.clone())));
    }
    let (mut dump, size) = open_dump(path, table)?;
    dump.seek(SeekFrom::Start(offset))?;
    let frame = read_frame(&mut dump, offset, size, table)?;
    if hex::encode(frame.hash) != hash {
        return Err(invalid("indexed offset points to a different record"));
    }
    Ok(Some((frame.key, frame.row)))
}

struct Frame {
    record: Record,
    key: String,
    row: Value,
    hash: [u8; 32],
    next: u64,
}

fn open_dump(path: &Path, table: &str) -> Result<(BufReader<File>, u64)> {
    let file = File::open(dump_path(path, table))?;
    let size = file.metadata()?.len();
    let mut stream = BufReader::new(file);
    let mut magic = [0; MAGIC.len()];
    stream.read_exact(&mut magic)?;
    if &magic != MAGIC {
        return Err(invalid(format!("{table}: invalid dump magic")));
    }
    Ok((stream, size))
}

fn read_frame(stream: &mut impl Read, offset: u64, size: u64, table: &str) -> Result<Frame> {
    if offset < MAGIC.len() as u64 || size.saturating_sub(offset) < HEADER {
        return Err(invalid("frame header outside dump"));
    }
    let mut lengths = [0; 8];
    let mut hash = [0; 32];
    stream.read_exact(&mut lengths)?;
    stream.read_exact(&mut hash)?;
    let compressed = u32::from_le_bytes(lengths[..4].try_into().unwrap()) as usize;
    let raw = u32::from_le_bytes(lengths[4..].try_into().unwrap()) as usize;
    if !(1..=MAX_COMPRESSED).contains(&compressed)
        || !(1..=MAX_RECORD).contains(&raw)
        || compressed as u64 > size - offset - HEADER
    {
        return Err(invalid("invalid frame length"));
    }
    let mut block = vec![0; compressed];
    stream.read_exact(&mut block)?;
    let raw_bytes = lz4::block::decompress(&block, Some(raw as i32))?;
    if raw_bytes.len() != raw {
        return Err(invalid("decompressed record size mismatch"));
    }
    let (record, key, row) = Record::parse(table, &raw_bytes)?;
    if digest(&key, &row)? != hash {
        return Err(invalid("record content hash mismatch"));
    }
    Ok(Frame {
        record,
        key,
        row,
        hash,
        next: offset + HEADER + compressed as u64,
    })
}

fn scan(path: &Path, table: &str, mut record: impl FnMut(Frame) -> Result<()>) -> Result<Index> {
    let (mut dump, size) = open_dump(path, table)?;
    let mut offset = MAGIC.len() as u64;
    let mut index = Index::new();
    let mut previous = String::new();
    while offset < size {
        let frame = read_frame(&mut dump, offset, size, table)?;
        if frame.key <= previous {
            return Err(invalid("duplicate or unordered record key"));
        }
        previous.clone_from(&frame.key);
        insert_hash(&mut index, &frame.hash, offset)?;
        offset = frame.next;
        record(frame)?;
    }
    Ok(index)
}

fn insert_hash(index: &mut Index, hash: &[u8; 32], offset: u64) -> Result<()> {
    if index.insert(hex::encode(hash), offset).is_some() {
        return Err(invalid("duplicate record content hash"));
    }
    Ok(())
}

fn check_table(table: &str) -> Result<()> {
    if !TABLES.contains(&table) {
        return Err(invalid(format!("unknown SPG table {table}")));
    }
    Ok(())
}

fn check_hash(hash: &str) -> Result<()> {
    if hash.len() != 64
        || !hash
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Err(invalid("invalid content hash"));
    }
    Ok(())
}

fn read_metadata(path: &Path) -> Result<Vec<u8>> {
    let mut data = Vec::new();
    File::open(path)?
        .take((MAX_METADATA + 1) as u64)
        .read_to_end(&mut data)?;
    if data.len() > MAX_METADATA {
        return Err(invalid("metadata exceeds byte limit"));
    }
    Ok(data)
}

fn dump_path(path: &Path, table: &str) -> std::path::PathBuf {
    path.join(format!("{table}.dump"))
}

fn index_path(path: &Path, table: &str) -> std::path::PathBuf {
    path.join(format!("{table}.index.json"))
}

fn json_bytes(value: &impl Serialize) -> Result<Vec<u8>> {
    let mut bytes = serde_json::to_vec(value)?;
    bytes.push(b'\n');
    if bytes.len() > MAX_METADATA {
        return Err(invalid("metadata exceeds byte limit"));
    }
    Ok(bytes)
}

fn write_json(mut output: impl Write, value: &impl Serialize) -> Result<()> {
    output.write_all(&json_bytes(value)?)?;
    Ok(())
}

fn read_index(path: &Path, table: &str) -> Result<Index> {
    let data = read_metadata(&index_path(path, table))?;
    let index: Index = serde_json::from_slice(&data)?;
    if json_bytes(&index)? != data {
        return Err(invalid(format!("{table}: noncanonical index")));
    }
    for (hash, &offset) in &index {
        check_hash(hash)?;
        if offset < MAGIC.len() as u64 {
            return Err(invalid(format!("{table}: invalid frame offset")));
        }
    }
    Ok(index)
}

fn write_index(path: &Path, table: &str, index: &Index) -> Result<()> {
    let mut file = NamedTempFile::new_in(path)?;
    write_json(&mut file, index)?;
    file.persist(index_path(path, table))
        .map_err(|error| error.error)?;
    Ok(())
}

fn parent(path: &Path) -> &Path {
    path.parent()
        .filter(|parent| !parent.as_os_str().is_empty())
        .unwrap_or(Path::new("."))
}

fn stage(path: &Path) -> Result<TempDir> {
    if path.symlink_metadata().is_ok() {
        return Err(invalid(format!(
            "destination already exists: {}",
            path.display()
        )));
    }
    Ok(tempdir_in(parent(path))?)
}

fn publish(staging: TempDir, destination: &Path) -> Result<()> {
    // Reserve the name exclusively. On Unix rename then replaces our empty directory.
    fs::create_dir(destination)?;
    if let Err(error) = fs::rename(staging.path(), destination) {
        let _ = fs::remove_dir(destination);
        return Err(error.into());
    }
    Ok(())
}

struct TextDump(Option<BufWriter<File>>, bool);

impl TextDump {
    fn open(path: &Path, table: &str, enabled: bool) -> Result<Self> {
        let mut output = None;
        if enabled {
            let mut file = BufWriter::new(File::create(path.join(format!("{table}.json")))?);
            file.write_all(b"[")?;
            output = Some(file);
        }
        Ok(Self(output, true))
    }

    fn record(&mut self, record: &Record) -> Result<()> {
        if let Some(output) = &mut self.0 {
            if !self.1 {
                output.write_all(b",")?;
            }
            output.write_all(b"\n")?;
            serde_json::to_writer(output, &record.proto_json())?;
            self.1 = false;
        }
        Ok(())
    }

    fn finish(self) -> Result<()> {
        if let Some(mut output) = self.0 {
            if !self.1 {
                output.write_all(b"\n")?;
            }
            output.write_all(b"]\n")?;
            output.flush()?;
        }
        Ok(())
    }
}
