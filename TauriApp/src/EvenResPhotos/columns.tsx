"use client";

import { ColumnDef } from "@tanstack/react-table";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { OddResMediaElement } from "@/jsonParse/OddPhotos";
import { Command } from "@tauri-apps/api/shell";

export const columns: ColumnDef<OddResMediaElement>[] = [
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
    accessorKey: "resolution",
    header: "Resolution",
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
  },
  {
    id: "status",
    header: "Status",
    enableHiding: false,
    cell: ({ row }) => {
      let statusIcon;
      let statusMessage = row.original.statusMessage || "Status not available"; // Fallback message
  
      switch (row.original.status) {
        case "Converted":
          statusIcon = "✅";
          break;
        case "Unconverted":
          statusIcon = "⚠️";
          break;
        case "Failed":
          statusIcon = "❌";
          break;
        default:
          statusIcon = "❔"; // Default icon if none of the cases match
          break;
      }
  
      return (
        <>
          <Popover>
            <PopoverTrigger>{statusIcon}</PopoverTrigger>
            <PopoverContent className="mx-5">
              {statusMessage}
            </PopoverContent>
          </Popover>
        </>
      );
    },
  }  
];
