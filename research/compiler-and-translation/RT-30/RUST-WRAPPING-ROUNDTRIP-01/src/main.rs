use std::{env, fs};
use syn::{File, Item, ItemFn};

fn recognize(source: &str) -> String {
    let File {
        shebang,
        attrs,
        mut items,
    } = match syn::parse_file(source) {
        Ok(file) => file,
        Err(_) => return "parse-error".into(),
    };
    if shebang.is_some() || !attrs.is_empty() || items.len() != 1 {
        return "unsupported-inventory".into();
    }
    let Item::Fn(mut input) = items.pop().expect("one item") else {
        return "unsupported-inventory".into();
    };
    input.sig.ident = syn::Ident::new("admitted", input.sig.ident.span());

    let operations = [
        ("wrap_add", "wrapping_add"),
        ("wrap_sub", "wrapping_sub"),
        ("wrap_mul", "wrapping_mul"),
    ];
    for (name, method) in operations {
        for left in ["a", "b"] {
            for right in ["a", "b"] {
                let fixture = format!(
                    "pub fn admitted(a: u32, b: u32, enabled: u32, emit: &mut dyn FnMut(u32),
                                     out: &mut u32) -> u32 {{
                        emit(a);
                        let mut value = b;
                        if enabled != 0 {{ value = {left}.{method}({right}); }}
                        emit(value);
                        *out = value;
                        0
                    }}"
                );
                let expected: ItemFn = syn::parse_str(&fixture).expect("internal template");
                if input == expected {
                    return format!("accepted {name} {left} {right}");
                }
            }
        }
    }
    "unsupported-shape".into()
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let file = env::args_os().nth(1).ok_or("expected Rust source path")?;
    println!("{}", recognize(&fs::read_to_string(file)?));
    Ok(())
}
