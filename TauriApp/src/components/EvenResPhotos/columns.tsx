"use client";

import { ColumnDef } from "@tanstack/react-table";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { SelectedMediaElement } from "@/jsonParse/SelectedMedia";
import TimecodeButton from "@/components/TimecodeButton";

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
    accessorKey: "resolution",
    header: "Resolution",
  },
  {
    accessorKey: "timecodes",
    header: "Current Timeline Timecode(s)",
    enableHiding: false,
    cell: ({ row }) => {
      const timecodes = row.original.timecodes;
  
      if (timecodes.length === 0) {
        return <Button disabled={true}>No Timecode</Button>;
      } else {
        return (
          <>
            {timecodes.map((tc, index) => (
              <TimecodeButton key={index} timecode={tc} />
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
