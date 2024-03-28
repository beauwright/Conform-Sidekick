import React from 'react';
import { Button } from "@/components/ui/button";
import { Command } from "@tauri-apps/api/shell";

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

  return (
    <Button className="my-1 mr-1" onClick={handleClick}>
      {timecode}
    </Button>
  );
};

export default TimecodeButton;
