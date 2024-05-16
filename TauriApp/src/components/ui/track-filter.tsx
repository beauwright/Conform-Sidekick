import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { ColumnFiltersState } from "@tanstack/react-table";
import { RadioGroup, RadioGroupItem } from "./radio-group";
import { Label } from "./label";

interface TrackFilterProps {
  setColumnFilters: (filters: ColumnFiltersState) => void;
}

export function TrackFilter({ setColumnFilters }: TrackFilterProps) {
  const [filterOption, setFilterOption] = useState("all");
  const [fromTrack, setFromTrack] = useState("");
  const [toTrack, setToTrack] = useState("");
  const applyFilter = () => {
    if (filterOption === "filter" && fromTrack && toTrack) {
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
      <RadioGroup
        defaultValue="all"
        value={filterOption}
        onValueChange={(value) => {
          setFilterOption(value);
        }}
      >
        <div className="flex items-center space-x-2">
          <RadioGroupItem value="all" id="all" />
          <Label htmlFor="all">All Tracks</Label>
        </div>
        <div className="flex items-center space-x-2">
          <RadioGroupItem value="filter" id="filter" />
          <Label htmlFor="filter">Filter Tracks</Label>
        </div>
      </RadioGroup>
      {filterOption === "filter" && (
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
  );
}
