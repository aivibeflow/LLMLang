//! Documentation resources packaged with this server build.

use serde_json::{json, Value};

pub const URI_PREFIX: &str = "llmlang://doc/";
pub const MIME_TYPE: &str = "text/markdown";
pub const INSTRUCTIONS: &str = "Start with llmlang://doc/bootstrap.md. Read documents with resources/read and find them in resources/list or llmlang://doc/index.md.";

const INDEX: &str = "index.md";
const INDEX_TITLE: &str = "LLMLang documentation";

struct Document {
    path: &'static str,
    title: &'static str,
    description: &'static str,
    text: &'static str,
}

const DOCUMENTS: &[Document] = &[
    Document {
        path: "bootstrap.md",
        title: "LLMLang agent bootstrap",
        description: "Start here to choose a workflow for building or editing a package.",
        text: include_str!("../../docs/bootstrap.md"),
    },
    Document {
        path: "server.md",
        title: "LLMLang Server over MCP",
        description: "MCP connection, tools, resources, and package workflows.",
        text: include_str!("../../docs/server.md"),
    },
    Document {
        path: "lang.md",
        title: "LLMLang syntax",
        description: "Language syntax and the scalar authoring format.",
        text: include_str!("../../docs/lang.md"),
    },
    Document {
        path: "examples.md",
        title: "LLMLang examples",
        description: "Example packages and their expected behavior.",
        text: include_str!("../../examples/README.md"),
    },
    Document {
        path: "rfc.md",
        title: "LLMLang architecture RFC",
        description: "Architecture, program graphs, bindings, storage, and verification.",
        text: include_str!("../../RFC.md"),
    },
];

pub fn list() -> Vec<Value> {
    let resource = |path: &str, title: &str, description: &str| {
        json!({
            "uri": format!("{URI_PREFIX}{path}"),
            "name": path,
            "title": title,
            "description": description,
            "mimeType": MIME_TYPE,
        })
    };
    let mut resources = vec![resource(
        INDEX,
        INDEX_TITLE,
        "Table of contents for the bundled documentation.",
    )];
    resources.extend(
        DOCUMENTS
            .iter()
            .map(|doc| resource(doc.path, doc.title, doc.description)),
    );
    resources
}

pub fn read(uri: &str, path: &str) -> Option<Value> {
    let text = if path == INDEX {
        let mut index = format!("# {INDEX_TITLE}\n\n");
        for doc in DOCUMENTS {
            index.push_str(&format!(
                "- [{}]({URI_PREFIX}{}) — {}\n",
                doc.title, doc.path, doc.description
            ));
        }
        json!(index)
    } else {
        json!(DOCUMENTS.iter().find(|doc| doc.path == path)?.text)
    };
    Some(json!({"contents": [{"uri":uri, "mimeType": MIME_TYPE, "text": text}]}))
}
