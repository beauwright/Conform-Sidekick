import { DataTable } from "../components/ui/data-table";
import { columns } from "./columns";
import { useEffect, useState } from "react";
import { Convert as ConvertOddResMedia, SelectedMediaElement } from "@/jsonParse/SelectedMedia";
import { Convert as ConvertConversionResults, ConversionResult } from "@/jsonParse/ConversionResult";
import { getObjectFromPythonSidecar } from "@/lib/utils";
import LoadingStatus from "@/LoadingStatus";
import ScopeSelector from "@/components/ScopeSelector"
async function getData(projOrTimelineSelected: string): Promise<SelectedMediaElement[]> {
  // Determine the argument based on the selected radio option
  const dataKey = projOrTimelineSelected === "timeline" ? ["oddResInTimeline"] : ["oddResInProject"];
  try {
    const oddResMedia = await getObjectFromPythonSidecar(
      dataKey,
      ConvertOddResMedia.toSelectedMedia
    );
    console.log("oddResMedia", oddResMedia);
    return oddResMedia.selectedMedia;
  } catch (error) {
    console.log("error fetching odd res photos data", error);
    return [];
  }
}

function EvenResPhotos() {
  const [showDataTable, setShowDataTable] = useState(false);
  const [tableData, setTableData] = useState<SelectedMediaElement[] | null>(null);
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
              <LoadingStatus loadingText={`${processedCount}/${totalCount} photos converted (${processedCount / totalCount * 100}%)`} />
            ) : (
              <DataTable
                columns={columns}
                data={tableData}
                buttonProps={{
                  buttonLabel: "Convert Selected Photos",
                  buttonFunction: convertSelectedPhotos
                }}
                rowSelection={rowSelection}
                setRowSelection={setRowSelection}
              />
            )}
          </div>
        ) : (
          <LoadingStatus loadingText="Finding odd resolution photos" />
        )
      ) : (
        <ScopeSelector setShowDataTable={setShowDataTable} projOrTimelineSelected={projOrTimelineSelected} setProjOrTimelineSelected={setProjOrTimelineSelected} typeOfMediaDisplayString="Odd Resolution Media"/>
      )}
    </>
  );
}

export default EvenResPhotos;
