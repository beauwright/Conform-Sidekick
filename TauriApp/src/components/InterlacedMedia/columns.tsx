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
    accessorKey: "fieldType",
    header: "Field Dominance",
  },
  {
    accessorKey: "clips",
    header: "Current Timeline Instance(s)",
    enableHiding: false,
    cell: ({ row }) => {
      const clips = row.original.clips;

      if (clips.length === 0) {
        return <Button disabled={true}>No Instances</Button>;
      } else {
        return (
          <>
            {clips.map((clip, index) => (
              <div key={index} className="flex items-center justify-center">
                <h3 className="text-lg pr-4">Track {clip.track}</h3>
                <TimecodeButton timecode={clip.timecode} />
              </div>
            ))}
          </>
        );
      }
    },
  },
  {
    id: 'track',
    header: 'Track',
    accessorFn: (originalRow) => originalRow.clips.map(clip => clip.track),
    cell: ({ getValue }) => getValue().join(", "),
    filterFn: 'rangeFilter',  // Reference the new filter function here
  }
];
