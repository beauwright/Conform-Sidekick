"use client";

import { ColumnDef } from "@tanstack/react-table";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
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
  }
];
