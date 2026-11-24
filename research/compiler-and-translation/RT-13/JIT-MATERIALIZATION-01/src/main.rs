mod checked_add {
    #![allow(dead_code)]
    include!("../../cranelift-checked-add/src/main.rs");

    pub fn run() -> Result<(), Box<dyn std::error::Error>> {
        let argv: Vec<String> = std::env::args().collect();
        if argv.len() != 3 || !matches!(argv[1].as_str(), "none" | "speed") {
            return Err("usage: latency-cranelift none|speed samples".into());
        }
        let samples = argv[2].parse::<usize>()?;
        for index in 0..samples {
            let start = std::time::Instant::now();
            let (module, entry, _clif, _machine) = make_entry(&argv[1], Policy::Preserving)?;
            let elapsed = start.elapsed().as_nanos();
            println!("time {index} {elapsed}");
            for (a, b, enabled) in [(3, 1, 1), (0x7fffffff, 1, 1), (7, 5, 0), (4, 3, 2)] {
                let mut output = 0xabad1234;
                let status = unsafe { entry(a, b, enabled, collect, &mut output) };
                print!("check {status} {output}");
                EVENTS.with_borrow_mut(|events| {
                    for value in events.drain(..) {
                        print!(" {value}");
                    }
                });
                println!();
            }
            // Entry is unused after this point and no generated function is running.
            unsafe { module.free_memory() };
        }
        Ok(())
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    checked_add::run()
}
