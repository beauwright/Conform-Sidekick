import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useResolveContext } from "@/ResolveContext";
import { DataTable } from "../components/ui/data-table";
import { columns } from "./columns";
import { useEffect, useState } from "react";
import { Convert, OddResMediaElement } from "@/jsonParse/OddPhotos";
import { getObjectFromPythonSidecar } from "@/lib/utils";
import ResolveConnectionStatus from "@/ResolveConnectionStatus";

async function getData(projOrTimelineSelected: string): Promise<OddResMediaElement[]> {
  // Determine the argument based on the selected radio option
  const dataKey = projOrTimelineSelected === "timeline" ? ["oddResInTimeline"] : ["oddResInProject"];
  try {
      const oddResMedia = await getObjectFromPythonSidecar(
          dataKey,
          Convert.toOddResMedia
      );
      console.log("oddResMedia", oddResMedia);
      return oddResMedia.oddResMedia;
  } catch (error) {
      console.log("error fetching odd res photos data", error);
      return [];
  }
}


interface ProjectInfoProps {
  setShowDataTable: (value: boolean) => void;
  projOrTimelineSelected: string;
  setProjOrTimelineSelected: (value: string) => void;
}

const ProjectInfo: React.FC<ProjectInfoProps> = ({ setShowDataTable, projOrTimelineSelected, setProjOrTimelineSelected }) => {
  const context = useResolveContext();
  const { currentProject, currentTimeline } = context || {};

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
            <h2 className="font-semibold">
              Where to Look For Odd Resolution Media
            </h2>
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
  const [tableData, setTableData] = useState<OddResMediaElement[] | null>(null);
  const [projOrTimelineSelected, setProjOrTimelineSelected] = useState("project");

  useEffect(() => {
    async function fetchData() {
      const data = await getData(projOrTimelineSelected);
      console.log("data is", data);
      setTableData(data);
    }
  
    if (showDataTable) {
      fetchData();
    }
  }, [showDataTable]);
  

  return (
    <>
      {showDataTable ? (
        tableData ? (
          <div className="w-11/12 mx-auto">
            <DataTable
              columns={columns}
              data={tableData}
              buttonLabel="Convert Selected Photos"
              buttonFunction={() => {}}
            />
          </div>
        ) : (
          <ResolveConnectionStatus loadingText="Finding odd resolution photos"/> // Show spinner here while tableData is null
        )
      ) : (
        <ProjectInfo setShowDataTable={setShowDataTable} projOrTimelineSelected={projOrTimelineSelected} setProjOrTimelineSelected={setProjOrTimelineSelected} />
      )}
    </>
  );
}

export default EvenResPhotos;
