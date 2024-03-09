"use client";

import { ColumnDef } from "@tanstack/react-table";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

// This type is used to define the shape of our data.
// You can use a Zod schema here if you want.
export type Media = {
  displayName: string;
  binPath: string;
  resolution: string;
  timecode: string[];
};

export const columns: ColumnDef<Media>[] = [
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
    accessorKey: "binPath",
    header: "Media Pool Location",
  },
  {
    accessorKey: "resolution",
    header: "Resolution",
  },
  {
    accessorKey: "timecode",
    header: "Current Timeline Timecode(s)",
    enableHiding: false,
    cell: ({ row }) => {
      const timecodes = row.original.timecode;

      // Check if the timecodes list is empty and return a disabled button if true
      if (timecodes.length === 0) {
        return <Button disabled={true}>No Timecode</Button>;
      } else {
        // Map each timecode to a Button component
        return (
          <>
            {timecodes.map((tc, index) => (
              <Button key={index} className="my-1 mr-1">{tc}</Button>
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

      return <>
      <Popover>
        <PopoverTrigger>
        ⚠️
        </PopoverTrigger>
        <PopoverContent className="mx-5">
          {row.original.displayName} has not been replaced.
        </PopoverContent>
      </Popover>
      </>;
    },
  },
];
