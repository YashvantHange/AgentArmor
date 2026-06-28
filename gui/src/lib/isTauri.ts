import { isTauri as tauriCoreIsTauri } from "@tauri-apps/api/core";

export function isTauri(): boolean {
  try {
    return tauriCoreIsTauri();
  } catch {
    return false;
  }
}

export async function openReportFolder(dirPath: string): Promise<void> {
  if (!isTauri()) return;
  const { open } = await import("@tauri-apps/plugin-shell");
  await open(dirPath);
}
