use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

static SIDECAR: Mutex<Option<Child>> = Mutex::new(None);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            spawn_sidecar(app.handle());
            Ok(())
        })
        .on_window_event(|_window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                kill_sidecar();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn spawn_sidecar(handle: &tauri::AppHandle) {
    let port = std::env::var("AGENTARMOR_PORT").unwrap_or_else(|_| "8787".into());
    let model_dir = resolve_model_dir(handle);

    let mut cmd = if let Some(exe) = resolve_agentarmor_exe(handle) {
        let mut c = Command::new(exe);
        c.args(["serve", "--port", &port, "--host", "127.0.0.1"]);
        c
    } else {
        let python = resolve_python(handle);
        let mut c = Command::new(&python);
        c.args([
            "-m",
            "agentarmor.cli.main",
            "serve",
            "--port",
            &port,
            "--host",
            "127.0.0.1",
        ]);
        c
    };

    if let Some(dir) = model_dir {
        cmd.args(["--model-dir", &dir]);
    }
    if let Some(data_dir) = resolve_data_dir(handle) {
        cmd.args(["--data-dir", &data_dir]);
    }

    cmd.stdout(Stdio::null()).stderr(Stdio::null());
    if let Ok(child) = cmd.spawn() {
        let mut guard = SIDECAR.lock().unwrap();
        *guard = Some(child);
        let _ = wait_for_health(&port, 60);
    }
}

fn resolve_agentarmor_exe(handle: &tauri::AppHandle) -> Option<String> {
    handle
        .path()
        .resource_dir()
        .ok()
        .map(|p| p.join("python").join("Scripts").join("agentarmor.exe"))
        .filter(|p| p.exists())
        .map(|p| p.to_string_lossy().into_owned())
}

fn resolve_python(handle: &tauri::AppHandle) -> String {
    if let Ok(res) = handle.path().resource_dir() {
        let embedded = res.join("python").join("python.exe");
        if embedded.exists() {
            return embedded.to_string_lossy().into_owned();
        }
    }
    std::env::var("AGENTARMOR_PYTHON").unwrap_or_else(|_| "python".into())
}

fn resolve_model_dir(handle: &tauri::AppHandle) -> Option<String> {
    handle
        .path()
        .resource_dir()
        .ok()
        .map(|p| p.join("models"))
        .filter(|p| p.exists())
        .map(|p| p.to_string_lossy().into_owned())
}

fn resolve_data_dir(handle: &tauri::AppHandle) -> Option<String> {
    let portable = std::env::var("AGENTARMOR_PORTABLE").ok().as_deref() == Some("1")
        || std::env::var("AGENTARMOR_DATA_DIR").is_ok();

    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            if dir.join("PORTABLE").exists() {
                let data = dir.join("data");
                let _ = std::fs::create_dir_all(&data);
                return Some(data.to_string_lossy().into_owned());
            }
        }
    }

    if portable {
        if let Ok(dir) = std::env::var("AGENTARMOR_DATA_DIR") {
            return Some(dir);
        }
    }
    None
}

fn wait_for_health(port: &str, max_secs: u64) -> bool {
    let url = format!("http://127.0.0.1:{port}/health");
    for _ in 0..max_secs * 2 {
        if ureq::get(&url).call().map(|r| r.status() == 200).unwrap_or(false) {
            return true;
        }
        std::thread::sleep(Duration::from_millis(500));
    }
    false
}

fn kill_sidecar() {
    let mut guard = SIDECAR.lock().unwrap();
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
    }
}
