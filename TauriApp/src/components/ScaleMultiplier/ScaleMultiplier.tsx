import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SelectSeparator } from "@radix-ui/react-select";
import { Input } from "../ui/input";
import LoadingStatus from "@/LoadingStatus";

interface ScaleMultiplierSetupProps {
  scaleTimeline: string;
  setScaleTimeline: (value: string) => void;
  scaleMultiplier: number;
  setScaleMultiplier: (value: number) => void;
  exportedFCPXML: string;
  setExportedFCPXML: (value: string) => void;
}

function ScaleMultiplierSetup({
  scaleTimeline,
  setScaleTimeline,
  scaleMultiplier,
  setScaleMultiplier,
  exportedFCPXML,
  setExportedFCPXML,
}: ScaleMultiplierSetupProps) {
  return (
    <>
      <div className="flex justify-center gap-2">
        <Button variant="secondary">Create a FCPXML of Current Timeline</Button>
        <Button variant="secondary">Modify Existing FCPXML</Button>
      </div>
      {scaleTimeline ? (
        <h2 className="dark:text-slate-300 truncate">{scaleTimeline}</h2>
      ) : (
        <h2 className="text-red-700 dark:text-red-300">
          Please generate A FCPXML of the current timeline or select a FCPXML to
          continue.
        </h2>
      )}
      <h2 className="dark:text-slate-50 font-semibold mt-4">
        Select the scaling type to modify
      </h2>
      <Select>
        <SelectTrigger className="w-[280px]">
          <SelectValue placeholder="Select scaling type" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Scaling Types</SelectItem>
          <SelectSeparator />
          <SelectGroup>
            <SelectLabel>Individual Scaling Types</SelectLabel>
            <SelectItem value="fit">Fit</SelectItem>
            <SelectItem value="fill">Fill</SelectItem>
            <SelectItem value="none">Crop</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
      <h2 className="dark:text-slate-50 font-semibold mt-4">
        Select the amount to multiply the scaling by
      </h2>
      <Input
        type="number"
        value={scaleMultiplier}
        onChange={(e) => setScaleMultiplier(parseInt(e.target.value))}
      />
      <Button>Apply Scaling to FCPXML</Button>
    </>
  );
}

function ScaleMultiplier() {
  const [scaleTimeline, setScaleTimeline] = useState("");
  const [scaleMultiplier, setScaleMultiplier] = useState(2);
  const [exportedFCPXML, setExportedFCPXML] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  return (
    <div className="flex justify-center select-none">
      <div className="max-w-80 px-5">
        {isExporting ? (
          <LoadingStatus loadingText="Exporting FCPXML" />
        ) : exportedFCPXML ? (
          <div className="flex flex-col gap-4">
            <h2 className="dark:text-slate-300 truncate">{exportedFCPXML}</h2>
            <Button>Import Modified FCPXML to current project</Button>
          </div>
        ) : (
          <ScaleMultiplierSetup
            scaleTimeline={scaleTimeline}
            setScaleTimeline={setScaleTimeline}
            scaleMultiplier={scaleMultiplier}
            setScaleMultiplier={setScaleMultiplier}
            exportedFCPXML={exportedFCPXML}
            setExportedFCPXML={setExportedFCPXML}
          />
        )}
      </div>
    </div>
  );
}

export default ScaleMultiplier;
