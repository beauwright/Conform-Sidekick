"use client";

import { ColumnDef } from "@tanstack/react-table";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { SelectedMediaElement } from "@/jsonParse/SelectedMedia";
import { Command } from "@tauri-apps/api/shell";

export const columns: ColumnDef<SelectedMediaElement>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <Checkbox
        checked={
          table.getIsAllPageRowsSelected() ||
          (table.getIsSomePageRowsSelected() && "indeterminate")
        }
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        aria-label="Select all"
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Select row"
      />
    ),
    enableSorting: false,
    enableHiding: false,
  },
  {
    accessorKey: "displayName",
    header: "Name",
  },
  {
    accessorKey: "binLocation",
    header: "Media Pool Location",
  },
  {
    accessorKey: "fieldType",
    header: "Field Dominance",
  },
  {
    accessorKey: "timecodes",
    header: "Current Timeline Timecode(s)",
    enableHiding: false,
    cell: ({ row }) => {
      const timecodes = row.original.timecodes;

      // Check if the timecodes list is empty and return a disabled button if true
      if (timecodes.length === 0) {
        return <Button disabled={true}>No Timecode</Button>;
      } else {
        // Map each timecode to a Button component
        return (
          <>
            {timecodes.map((tc, index) => (
              <Button
                key={index}
                className="my-1 mr-1"
                onClick={() => {
                  async function sidecar(arg: string[]) {
                    const sidecar = await Command.sidecar(
                      "../../PythonInterface/dist/even_photos_resolve",
                      arg
                    ).execute();
                    console.log("stdout: ", sidecar.stdout, "stderr: ", sidecar.stderr)
                  }
                  const arg = ["jumpToTimecode", "--tc", tc]
                  console.log("arg was ", arg)
                  sidecar(arg);
                }}
              >
                {tc}
              </Button>
            ))}
          </>
        );
      }
    },
  }  
];
