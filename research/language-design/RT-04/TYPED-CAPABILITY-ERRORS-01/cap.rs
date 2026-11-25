pub struct Authority(u8);
pub struct Read<'a>(&'a Authority);
pub struct Audit<'a>(&'a Authority);
pub struct Write<'a>(&'a Authority);

#[derive(Debug)]
pub enum ReadError {
    Missing,
    Busy,
}

#[derive(Debug)]
pub enum Error {
    DeniedRead,
    DeniedAudit,
    DeniedWrite,
    Busy,
    AuditFailure,
    WriteFailure,
}

impl Authority {
    fn from_fixture_mask(mask: u8) -> Self {
        Self(mask & 7)
    }

    pub fn reader(&self) -> Option<Read<'_>> {
        (self.0 & 1 != 0).then_some(Read(self))
    }

    pub fn auditor(&self) -> Option<Audit<'_>> {
        (self.0 & 2 != 0).then_some(Audit(self))
    }

    pub fn writer(&self) -> Option<Write<'_>> {
        (self.0 & 4 != 0).then_some(Write(self))
    }
}

pub fn read(grant: Read<'_>, mode: u8, events: &mut Vec<&'static str>) -> Result<u8, ReadError> {
    assert!(grant.0.0 & 1 != 0);
    events.push("read");
    match mode {
        0 => Ok(7),
        1 => Err(ReadError::Missing),
        _ => Err(ReadError::Busy),
    }
}

pub fn audit(grant: Audit<'_>, fails: bool, events: &mut Vec<&'static str>) -> Result<(), Error> {
    assert!(grant.0.0 & 2 != 0);
    events.push("audit");
    if fails { Err(Error::AuditFailure) } else { Ok(()) }
}

pub fn write(grant: Write<'_>, fails: bool, events: &mut Vec<&'static str>) -> Result<(), Error> {
    assert!(grant.0.0 & 4 != 0);
    events.push("write");
    if fails { Err(Error::WriteFailure) } else { Ok(()) }
}

pub fn pipeline(authority: &Authority, input: u8, audit_mode: u8, write_mode: u8,
                events: &mut Vec<&'static str>) -> Result<Option<u8>, Error> {
    let value = match read(authority.reader().ok_or(Error::DeniedRead)?, input, events) {
        Ok(value) => value,
        Err(ReadError::Missing) => return Ok(None),
        Err(ReadError::Busy) => return Err(Error::Busy),
    };
    if audit_mode != 0 {
        audit(authority.auditor().ok_or(Error::DeniedAudit)?, audit_mode == 2, events)?;
    }
    if write_mode != 0 {
        write(authority.writer().ok_or(Error::DeniedWrite)?, write_mode == 2, events)?;
    }
    Ok(Some(value))
}

// Synthetic inputs exercise the closed model without exporting authority.
pub fn observe_fixture(mask: u8, input: u8, audit_mode: u8, write_mode: u8,
                       events: &mut Vec<&'static str>) -> Result<Option<u8>, Error> {
    pipeline(&Authority::from_fixture_mask(mask), input, audit_mode, write_mode, events)
}
