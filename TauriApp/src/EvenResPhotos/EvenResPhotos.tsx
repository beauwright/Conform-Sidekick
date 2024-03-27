import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useResolveContext } from "@/ResolveContext";
import { DataTable } from "../components/ui/data-table";
import { columns } from "./columns";
import { useEffect, useState } from "react";
import { Convert as ConvertOddResMedia, OddResMediaElement } from "@/jsonParse/OddPhotos";
import { Convert as ConvertConversionResults, ConversionResult } from "@/jsonParse/ConversionResult";
import { getObjectFromPythonSidecar } from "@/lib/utils";
import LoadingStatus from "@/LoadingStatus";

async function getData(projOrTimelineSelected: string): Promise<OddResMediaElement[]> {
  // Determine the argument based on the selected radio option
  const dataKey = projOrTimelineSelected === "timeline" ? ["oddResInTimeline"] : ["oddResInProject"];
  try {
    const oddResMedia = await getObjectFromPythonSidecar(
      dataKey,
      ConvertOddResMedia.toOddResMedia
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
  type RowSelection = { [key: number]: boolean };
  // Table state
  const [rowSelection, setRowSelection] = useState<RowSelection>({});
  // Conversion UI states
  const [isConverting, setIsConverting] = useState(false);
  const [processedCount, setProcessedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);



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


  const convertSelectedPhotos = async () => {
    if (tableData) {
      const selectedRows = tableData.filter((_, index) => rowSelection[index]);
      setTotalCount(selectedRows.length); // Set total count of photos to be converted
      setProcessedCount(0); // Reset processed count
      setIsConverting(true); // Indicate conversion process is starting
      const updatedData = [...tableData]; // Make a shallow copy of the table data

      for (const [index, photo] of selectedRows.entries()) {
        try {
          const conversionResult: ConversionResult = await getObjectFromPythonSidecar(
            ["convertOddResPhoto", "--binLocation", photo.binLocation, "--mediaId", photo.mediaId],
            ConvertConversionResults.toConversionResult
          );

          // Update the status in the copied data array
          if (conversionResult.success) {
            updatedData[index].status = "Converted";
            updatedData[index].statusMessage = `Converted photo located at: ${conversionResult.file_path}`;
          } else {
            updatedData[index].status = "Failed";
            if (conversionResult.error_message) {
              updatedData[index].statusMessage = conversionResult.error_message;
            }
          }
        } catch (error) {
          updatedData[index].status = "Failed";
          updatedData[index].statusMessage = "Photo conversion process did not run as expected.";
        } finally {
          // Increase the processed count each time a photo is processed
          setProcessedCount((prevCount) => prevCount + 1);
        }
      }

      // When all photos are processed, update the data and indicate conversion process is done
      setTableData(updatedData);
      setIsConverting(false);
    }
  };


  return (
    <>
      {showDataTable ? (
        tableData ? (
          <div className="w-11/12 mx-auto">
            {isConverting ? (
              <LoadingStatus loadingText={`${processedCount}/${totalCount} photos converted (${processedCount / totalCount}%)`} />
            ) : (
              <DataTable
                columns={columns}
                data={tableData}
                buttonLabel="Convert Selected Photos"
                buttonFunction={convertSelectedPhotos}
                rowSelection={rowSelection}
                setRowSelection={setRowSelection}
              />
            )}
          </div>
        ) : (
          <LoadingStatus loadingText="Finding odd resolution photos" />
        )
      ) : (
        <ProjectInfo setShowDataTable={setShowDataTable} projOrTimelineSelected={projOrTimelineSelected} setProjOrTimelineSelected={setProjOrTimelineSelected} />
      )}
    </>
  );
}

export default EvenResPhotos;
