import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useWebSocket } from "@/ResolveContext";
import { DataTable } from "../components/ui/data-table";
import { Media, columns } from "./columns";
import { useEffect, useState } from "react";
async function getData(): Promise<Media[]> {
  // Fetch data from your API here.
  return [
    {
      displayName: "File",
      resolution: "101x2000",
      binPath: "bin1/file.mov",
      timecode: ["1:00:00:00", "1:00:00:30"]
    },
    {
      displayName: "File 2",
      resolution: "1001x2000",
      binPath: "bin1/file2.mov",
      timecode: []
    },
  ];
}

const data = await getData();

interface ProjectInfoProps {
  setShowDataTable: (value: boolean) => void;
}

const ProjectInfo:React.FC<ProjectInfoProps> = ({ setShowDataTable }) => {
  const context = useWebSocket();
  const { currentProject, currentTimeline } = context || {};
  const [projOrTimelineSelected, setProjOrTimelineSelected] = useState("project");

  useEffect(() => {
    if (currentTimeline === "") {
      setProjOrTimelineSelected("project");
    }
  }, [currentTimeline]);
  return (
    <>
      <div className="flex justify-center">
        <h2 className="dark:text-slate-300 text-sm px-5 italic">
          Current Project: {currentProject}
        </h2>
        <h2 className="dark:text-slate-300 text-sm px-5 italic">
          Current Timeline: {currentTimeline}
        </h2>
      </div>
      <div className="flex justify-center ">
        <div className="flex m-2 w-1/2 justify-around bg-slate-50/60 dark:bg-slate-800 rounded dark:text-white">
          <RadioGroup
            defaultValue="project"
            value={projOrTimelineSelected}
            onValueChange={(value) => {
              setProjOrTimelineSelected(value);
            }}
            className="p-5"
          >
            <h2 className="font-semibold">Where to Look For Odd Resolution Media</h2>
            <div className="flex items-center gap-1">
              <RadioGroupItem value="project" id="project" />
              <Label htmlFor="r1">Project-wide</Label>
            </div>
            <div className="flex items-center gap-1">
              <RadioGroupItem
                value="timeline"
                id="timeline"
                disabled={currentTimeline === ""}
              />
              <Label htmlFor="r2">Current Timeline</Label>
            </div>
          </RadioGroup>
        </div>
      </div>
      <div className="flex justify-center p-5">
        <Button
          onClick={() => {
            setShowDataTable(true);
          }}
        >
          Run
        </Button>
      </div>
    </>
  );
};

// Main component
function EvenResPhotos() {
  const [showDataTable, setShowDataTable] = useState(false);

  return (
    <>
      {showDataTable === false ? (
        <ProjectInfo setShowDataTable={setShowDataTable} />
      ) : (
        <div className="w-11/12 mx-auto">
          <DataTable columns={columns} data={data} buttonLabel="Convert Selected Photos" buttonFunction={() => {}}/>
        </div>
      )}
    </>
  );
}

export default EvenResPhotos;
