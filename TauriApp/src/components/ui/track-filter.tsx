import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { ColumnFiltersState } from "@tanstack/react-table";

interface TrackFilterProps {
    setColumnFilters: (filters: ColumnFiltersState) => void;
  }

export function TrackFilter({ setColumnFilters }: TrackFilterProps) {
  const [filterOption, setFilterOption] = useState("all");
  const [fromTrack, setFromTrack] = useState("");
  const [toTrack, setToTrack] = useState("");
  const applyFilter = () => {
    if (filterOption === "range" && fromTrack && toTrack) {
      setColumnFilters([
        {
          id: "track",
          value: { from: parseInt(fromTrack, 10), to: parseInt(toTrack, 10) },
        },
      ]);
    } else {
      console.log("clearing");
      setColumnFilters([]); // Clear filters when "All Tracks" is selected
    }
  };

  useEffect(() => {
    applyFilter();
  }, [filterOption, fromTrack, toTrack]);

  return (
    <div>
      <div>
        <input
          type="radio"
          name="trackFilter"
          value="all"
          checked={filterOption === "all"}
          onChange={() => {
            setFilterOption("all");
          }}
          className="mr-1"
        />{" "}
        All Tracks
        <input
          type="radio"
          name="trackFilter"
          value="range"
          checked={filterOption === "range"}
          onChange={() => setFilterOption("range")}
          className="ml-2 m-1"
        />
        Range:
        {filterOption === "range" && (
          <div className="flex m-2">
            <Input
              type="number"
              placeholder="From Track"
              value={fromTrack}
              onChange={(e) => setFromTrack(e.target.value)}
              className="m-2"
            />
            <Input
              type="number"
              placeholder="To Track"
              value={toTrack}
              onChange={(e) => setToTrack(e.target.value)}
              className="m-2"
            />
          </div>
        )}
      </div>
    </div>
  );
}
