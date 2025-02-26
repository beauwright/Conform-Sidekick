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
import { getObjectFromPythonSidecar } from "@/lib/utils";
import { ConversionResultSchema } from "@/jsonParse/ConversionResult";
import { Toaster } from "@/components/ui/toaster";
import { useToast } from "@/components/ui/use-toast";
import { dirname } from '@tauri-apps/api/path';


interface ScaleMultiplierSetupProps {
  scaleTimeline: string;
  setScaleTimeline: (value: string) => void;
  scaleMultiplier: number;
  setScaleMultiplier: (value: number) => void;
  exportedFCPXML: string;
  setExportedFCPXML: (value: string) => void;
  isExporting: boolean;
  setIsExporting: (value: boolean) => void;
}

function ScaleMultiplierSetup({
  scaleTimeline,
  setScaleTimeline,
  scaleMultiplier,
  setScaleMultiplier,
  setExportedFCPXML,
  setIsExporting,
}: ScaleMultiplierSetupProps) {
  const { toast } = useToast();

  const getFCPXMLFromTimeline = async () => {
    setIsExporting(true);
    try {
      const fcpXMLResult = await getObjectFromPythonSidecar(
        ["exportCurrentTimelineFCPXML"],
        ConversionResultSchema.parse
      );
      if (fcpXMLResult.success) {
        setScaleTimeline(fcpXMLResult.file_path!);
      } else {
        toast({
          variant: "destructive",
          title: `Error exporting FCPXML`,
          description: fcpXMLResult.error_message,
        });
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "An unexpected error occurred";
      toast({
        variant: "destructive",
        title: `Error exporting FCPXML`,
        description: errorMessage,
      });
    }
    setIsExporting(false);
  };

  const importFCPXMLToTimeline = async (xmlPath: string) => {
    try {
      console.log("importing XML at:", xmlPath)
      const importResult = await getObjectFromPythonSidecar(
        ["importFCPXML", "--fcpxmld", xmlPath],
        ConversionResultSchema.parse
      );
      if (importResult.success) {
        toast({
          variant: "default",
          title: `Conform Sidekick successfully imported the modified XML into the current project`,
        });
      } else {
        toast({
          variant: "destructive",
          title: `Conform Sidekick ran into an error trying to import the modified XML`,
          description: importResult.error_message,
        });
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "An unexpected error occurred";
      toast({
        variant: "destructive",
        title: `Error exporting FCPXML`,
        description: errorMessage,
      });
    }
  };

  const applyScalingToFCPXML = async () => {
    setIsExporting(true);
    //TODO: Add scaling type when one is selected
    /*  
    const modifiedFcpResult = await getObjectFromPythonSidecar(
        ["modifyFCPXMLScaling", "--fcpXMLPath", scaleTimeline, "--scalingType", "all", "--scalingMultiplier", scaleMultiplier.toString()],
        ConversionResultSchema.parse
      );
      */
    try {
      const fileDir = await dirname(scaleTimeline);
      console.log("calling modify XML for ", scaleTimeline)
      const modifiedFcpResult = await getObjectFromPythonSidecar(
        [
          "modifyFCPXMLScaling",
          "--fcpxmld",
          scaleTimeline,
          "--scalingValue",
          scaleMultiplier.toString(),
          "--saveScaledFCPXMLDName",
          crypto.randomUUID().toString(),
          "--saveScaledFCPXMLDPath",
          // scaleTimeline is a string of a filepath of a different file in the directory we want to save the new file
          // so we need to get the directory of the file
          fileDir
        ],
        ConversionResultSchema.parse
      );
      if (modifiedFcpResult.success && modifiedFcpResult.file_path) {
        console.log("successfully modified the XML", modifiedFcpResult)
        setExportedFCPXML(modifiedFcpResult.file_path);
        console.log("calling to import", modifiedFcpResult.file_path)
        importFCPXMLToTimeline(modifiedFcpResult.file_path);
      } else {
        toast({
          variant: "destructive",
          title: `Conform Sidekick ran into an error trying to create a modified XML`,
          description: modifiedFcpResult.error_message,
        });
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "An unexpected error occurred";
      toast({
        variant: "destructive",
        title: `Error exporting FCPXML`,
        description: errorMessage,
      });
    }
    setIsExporting(false);
  };

  return (
    <>
      <div className="flex justify-center gap-2">
        <Button variant="secondary" onClick={getFCPXMLFromTimeline}>
          Create a FCPXML of Current Timeline
        </Button>
        <Button variant="secondary">Modify Existing FCPXML</Button>
      </div>
      {scaleTimeline ? (
        <h2 className="dark:text-slate-300 break-all">
          Timeline located at {scaleTimeline}
        </h2>
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
      <Button className="mt-4" onClick={applyScalingToFCPXML}>
        Apply Scaling to FCPXML
      </Button>
    </>
  );
}

function ScaleMultiplier() {
  const [scaleTimeline, setScaleTimeline] = useState("");
  const [scaleMultiplier, setScaleMultiplier] = useState(2);
  const [exportedFCPXML, setExportedFCPXML] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  return (
    <div className="flex justify-center">
      <Toaster />
      <div className="max-w-80 px-5">
        {isExporting ? (
          <LoadingStatus loadingText="Exporting FCPXML" />
        ) : exportedFCPXML ? (
          <div className="flex flex-col gap-4">
            <h2 className="dark:text-slate-300">{exportedFCPXML}</h2>
          </div>
        ) : (
          <ScaleMultiplierSetup
            scaleTimeline={scaleTimeline}
            setScaleTimeline={setScaleTimeline}
            scaleMultiplier={scaleMultiplier}
            setScaleMultiplier={setScaleMultiplier}
            exportedFCPXML={exportedFCPXML}
            setExportedFCPXML={setExportedFCPXML}
            isExporting={isExporting}
            setIsExporting={setIsExporting}
          />
        )}
      </div>
    </div>
  );
}

export default ScaleMultiplier;
