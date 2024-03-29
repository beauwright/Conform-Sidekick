import { columns } from "./columns";
import { useState } from "react";
import { Convert as ConvertOddResMedia, SelectedMediaElement } from "@/jsonParse/SelectedMedia";
import { Convert as ConvertConversionResults, ConversionResult } from "@/jsonParse/ConversionResult";
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
  const [processedCount, setProcessedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);


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
    <div className="w-11/12 mx-auto">
      {isConverting ? (
        <LoadingStatus loadingText={`${processedCount}/${totalCount} photos converted (${processedCount / totalCount * 100}%)`} />
      ) : (
        <MediaTable
          typeOfMediaDisplayString="Odd Resolution Media"
          dataFetchParameters={{
            projectKey: "oddResInProject",
            timelineKey: "oddResInTimeline",

            conversionFunction: ConvertOddResMedia.toSelectedMedia,
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
        />
      )}
    </div>
  );
}
export default EvenResPhotos;