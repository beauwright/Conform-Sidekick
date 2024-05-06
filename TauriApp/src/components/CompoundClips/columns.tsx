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
                <h3 className="pr-4 min-w-16">Track {clip.track}</h3>
                <TimecodeButton timecode={clip.timecode} />
              </div>
            ))}
          </>
        );
      }
    },
  },
  {
    id: "track",
    header: "Track(s)",
    accessorFn: (originalRow) => {
      // Use a Set to collect unique track numbers
      const uniqueTracks = new Set();
      originalRow.clips.forEach((clip) => uniqueTracks.add(clip.track));
      return Array.from(uniqueTracks); // Convert the Set back to an array
    },
    cell: ({ getValue }) => {
      const tracks: number[] = getValue() as number[];
      return tracks.join(", ");
    },
    filterFn: "rangeFilter",
  },
];
