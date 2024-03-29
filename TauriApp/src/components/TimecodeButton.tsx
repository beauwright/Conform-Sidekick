import React from 'react';
import { Button } from "@/components/ui/button";
import { Command } from "@tauri-apps/api/shell";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useToast } from "@/components/ui/use-toast"
import { Toaster } from './ui/toaster';

interface TimecodeButtonProps {
  timecode: string;
}

const TimecodeButton: React.FC<TimecodeButtonProps> = ({ timecode }) => {
  const handleClick = async () => {
    const sidecarCommand = "../../PythonInterface/dist/even_photos_resolve";
    const args = ["jumpToTimecode", "--tc", timecode];
    console.log("args:", args);
    try {
      const result = await Command.sidecar(sidecarCommand, args).execute();
      console.log("stdout:", result.stdout, "stderr:", result.stderr);
    } catch (error) {
      console.error("Error executing sidecar command:", error);
    }
  };
  const { toast } = useToast();

  return (
    <>
      <Toaster />
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button className="my-1 mr-1">{timecode}</Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel>Timecode Controls</DropdownMenuLabel>
          <DropdownMenuItem onClick={() => {
            navigator.clipboard.writeText(timecode);
            toast({
              description: "Timecode copied to clipboard."
            });
          }}>
            Copy Timecode
          </DropdownMenuItem>
          <DropdownMenuItem onClick={handleClick}>Go to Timecode</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu></>
  );
};

export default TimecodeButton;
