import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import { Command } from "@tauri-apps/api/shell";
import { readTextFile, removeFile, BaseDirectory } from "@tauri-apps/api/fs";

// tailwind merge
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
type ConvertFunction<T> = (json: string) => T;

export async function getObjectFromPythonSidecar<T>(cmdParams: string[], convertFunction: ConvertFunction<T>): Promise<T> {
  const command = Command.sidecar("../../PythonInterface/dist/even_photos_resolve", cmdParams);
  const output = await command.execute();
  console.log("cmdParams", cmdParams, "command", command, "stdOut", output.stdout, "stdErr", output.stderr)
  const tempOutput = JSON.parse(output.stdout);
  const json = await readTextFile(tempOutput.path, { dir: BaseDirectory.Temp });
  console.log(json);
  //await removeFile(tempOutput.path, { dir: BaseDirectory.Temp });
  const convertedData = convertFunction(json);

  return convertedData;
};