import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import { Command } from "@tauri-apps/api/shell";
import { readTextFile, removeFile, BaseDirectory } from "@tauri-apps/api/fs";
//import { Convert as ConvertOddPhotos, OddResMedia } from "./jsonParse/OddPhotos";
import { Convert as ConvertResolveConnections } from "./jsonParse/ResolveConnections";

interface ResolveContextType {
  currentProject: string;
  currentTimeline: string;
}

const ResolveContext = createContext<ResolveContextType | null>(null);

export const useWebSocket = () => {
  return useContext(ResolveContext);
};

interface ResolveProviderProps {
  children: ReactNode; // This line specifies that children can be any valid React node
}

export const ResolveProvider = ({ children }: ResolveProviderProps) => {
  // Use the interface here
  const [currentProject, setCurrentProject] = useState("");
  const [currentTimeline, setCurrentTimeline] = useState("");

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | null = null;
    const fetchProjectAndTimeline = async () => {
      try {
        //console.log("calling python")
        //console.log("before python call:", Date.now().toString())
        const command = Command.sidecar(
          "../../PythonInterface/dist/even_photos_resolve",
          "projectAndTimeline"
        );
        const output = await command.execute();

        //console.log("after python call:", output.stdout, Date.now().toString());
        //console.log(output.stderr);
        let outputStr = output.stdout.replace("\r\n", "")
        outputStr.replace("\n", "")

        const json = await readTextFile(outputStr, {dir: BaseDirectory.Temp});
        //console.log("json contents:", json);

        await removeFile(outputStr, {dir: BaseDirectory.Temp});
        //console.log("after delete", Date.now().toString())
        const projectAndTimeline =
          ConvertResolveConnections.toResolveConnection(json);
        setCurrentProject(projectAndTimeline.projectName);

        if (projectAndTimeline.timelineName) {
          setCurrentTimeline(projectAndTimeline.timelineName);
        } else {
          setCurrentTimeline("");
        }
      } catch (error) {
        setCurrentProject("");
        console.log(error);
      }
      console.log("after assignments to state", Date.now().toString())
    };

    fetchProjectAndTimeline(); // Initial fetch
    intervalId = setInterval(fetchProjectAndTimeline, 4000); // Fetch every 4 seconds

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, []);

  const value = {
    currentProject,
    currentTimeline,
  };

  return (
    <ResolveContext.Provider value={value}>{children}</ResolveContext.Provider>
  );
};
