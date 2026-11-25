use provider::Value;

#[cfg(require_send)]
fn check_send<T: Send>(_: &T) {}

fn main() {
    let result = provider::value();
    #[cfg(require_send)]
    check_send(&result);
    println!("{}:{}", result.sum(), std::mem::size_of_val(&result));
}
