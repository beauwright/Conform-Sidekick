import { columns } from "./columns";
import { useState } from "react";
import { SelectedMediaSchema, SelectedMediaElement } from "@/jsonParse/SelectedMedia";
import { ConversionResultSchema, ConversionResult } from "@/jsonParse/ConversionResult";
import { getObjectFromPythonSidecar } from "@/lib/utils";
import LoadingStatus from "@/LoadingStatus";
import MediaTable from "@/components/MediaTable";

function EvenResPhotos() {
  const [tableData, setTableData] = useState<SelectedMediaElement[] | null>(null);
  type RowSelection = { [key: number]: boolean };
  // Table state
  const [rowSelection, setRowSelection] = useState<RowSelection>({});
  // Conversion UI states
  const [isConverting, setIsConverting] = useState(false);
  const [isConversionDone, setIsConversionDone] = useState(false);
  const [processedCount, setProcessedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);


  const convertSelectedPhotos = async () => {
    if (tableData) {
      const selectedRows = tableData.filter((_, index) => rowSelection[index]);
      setTotalCount(selectedRows.length); // Set total count of photos to be converted
      setProcessedCount(0); // Reset processed count
      setIsConverting(true); // Indicate conversion process is starting
      const updatedData = [...tableData]; // Make a shallow copy of the table data

      for (const [, photo] of selectedRows.entries()) {
        try {
          if (photo.status === "Converted") {
            continue;
          }

          const conversionResult: ConversionResult = await getObjectFromPythonSidecar(
            ["convertOddResPhoto", "--binLocation", photo.binLocation, "--mediaId", photo.mediaId],
            ConversionResultSchema.parse
          );

          // Update the status in the copied data array
          if (conversionResult.success) {
            for (let entry of updatedData) {
              if (entry.mediaId == photo.mediaId) {
                entry.status = "Converted";
                entry.statusMessage = `Converted photo located at: ${conversionResult.file_path}`;
                break;
              }
            }
          } else {
            for (let entry of updatedData) {
              if (entry.mediaId == photo.mediaId) {
                entry.status = "Failed";
                if (conversionResult.error_message) {
                  entry.statusMessage = conversionResult.error_message;
                }
                break;
              }
            }
          }
        } catch (error) {
          for (let entry of updatedData) {
            if (entry.mediaId == photo.mediaId) {
              entry.status = "Failed";
              entry.statusMessage = "Photo conversion process did not run as expected.";
              break;
            }
          }
        } finally {
          // Increase the processed count each time a photo is processed
          setProcessedCount((prevCount) => prevCount + 1);
        }
      }

      // When all photos are processed, update the data and indicate conversion process is done
      setTableData(updatedData);
      setIsConverting(false);
      setIsConversionDone(true);
    }
  };


  return (
    <div className="w-11/12 mx-auto">
      {isConverting ? (
        <LoadingStatus loadingText={`${processedCount}/${totalCount} photos converted (${Math.round(processedCount / totalCount * 100)}%)`} />
      ) : (
        <MediaTable
          typeOfMediaDisplayString="Odd Resolution Media"
          dataFetchParameters={{
            projectKey: "oddResInProject",
            timelineKey: "oddResInTimeline",

            conversionFunction: SelectedMediaSchema.parse,
          }}
          selection={rowSelection}
          setSelection={setRowSelection}
          columns={columns}
          buttonProps={{
            buttonLabel: "Convert Selected Photos",
            buttonFunction: convertSelectedPhotos
          }}
          tableData={tableData}
          setTableData={setTableData}
          showDataTableProp={isConversionDone}
        />
      )}
    </div>
  );
}
export default EvenResPhotos;
