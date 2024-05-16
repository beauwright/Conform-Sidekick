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
  //const uuid = crypto.randomUUID()
  //console.log("calling sidecar file with args: ", cmdParams, "time:", new Date, "uuid: ", uuid.toString())
  const command = Command.sidecar("../../PythonInterface/dist/even_photos_resolve", cmdParams);
  const output = await command.execute();
  //console.log("sidecar file returned result for args: ", cmdParams, "time:", new Date, "uuid: ", uuid.toString())
  //console.log("cmdParams", cmdParams, "command", command, "stdOut", output.stdout, "stdErr", output.stderr)
  const tempOutput = JSON.parse(output.stdout);
  let json = await readTextFile(tempOutput.path, { dir: BaseDirectory.Temp });
  json = JSON.parse(json);
  await removeFile(tempOutput.path, { dir: BaseDirectory.Temp });
  const convertedData = convertFunction(json);

  return convertedData;
};