use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use tauri::Manager;

static SIDECAR: Mutex<Option<Child>> = Mutex::new(None);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let handle = app.handle().clone();
            thread::spawn(move || spawn_sidecar(&handle));
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
    let mut cmd = build_sidecar_command(handle, &port);

    if let Some(dir) = resolve_model_dir(handle) {
        cmd.args(["--model-dir", &dir]);
    }
    if let Some(data_dir) = resolve_data_dir(handle) {
        cmd.args(["--data-dir", &data_dir]);
    }

    cmd.stdout(Stdio::null()).stderr(Stdio::null());
    hide_console_window(&mut cmd);

    if let Ok(child) = cmd.spawn() {
        let mut guard = SIDECAR.lock().unwrap();
        *guard = Some(child);
    }
}

fn build_sidecar_command(handle: &tauri::AppHandle, port: &str) -> Command {
    let host = "127.0.0.1";
    if let Some(python) = resolve_embedded_python(handle) {
        let mut cmd = Command::new(python);
        cmd.args([
            "-m",
            "agentarmor.cli.main",
            "serve",
            "--port",
            port,
            "--host",
            host,
        ]);
        return cmd;
    }

    let python = std::env::var("AGENTARMOR_PYTHON").unwrap_or_else(|_| "python".into());
    let mut cmd = Command::new(&python);
    cmd.args([
        "-m",
        "agentarmor.cli.main",
        "serve",
        "--port",
        port,
        "--host",
        host,
    ]);
    cmd
}

#[cfg(windows)]
fn hide_console_window(cmd: &mut Command) {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    cmd.creation_flags(CREATE_NO_WINDOW);
}

#[cfg(not(windows))]
fn hide_console_window(_cmd: &mut Command) {}

fn resolve_embedded_python(handle: &tauri::AppHandle) -> Option<String> {
    let res = handle.path().resource_dir().ok()?;
    let pythonw = res.join("python").join("pythonw.exe");
    if pythonw.exists() {
        return Some(pythonw.to_string_lossy().into_owned());
    }
    let python = res.join("python").join("python.exe");
    if python.exists() {
        return Some(python.to_string_lossy().into_owned());
    }
    None
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
    if std::env::var("AGENTARMOR_PORTABLE").ok().as_deref() == Some("1")
        || std::env::var("AGENTARMOR_DATA_DIR").is_ok()
    {
        if let Ok(dir) = std::env::var("AGENTARMOR_DATA_DIR") {
            return Some(dir);
        }
    }

    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            if dir.join("PORTABLE").exists() {
                let data = dir.join("data");
                let _ = std::fs::create_dir_all(&data);
                return Some(data.to_string_lossy().into_owned());
            }
        }
    }

    None
}

fn kill_sidecar() {
    let mut guard = SIDECAR.lock().unwrap();
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
    }
}
