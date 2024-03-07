import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import { Command } from "@tauri-apps/api/shell";
import { readTextFile, removeFile, BaseDirectory, readDir , writeTextFile} from "@tauri-apps/api/fs";
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
        console.log("calling python")
        const command = Command.sidecar(
          "../../PythonInterface/dist/even_photos_resolve",
          "projectAndTimeline"
        );
        const output = await command.execute();

        console.log(output.stdout);
        console.log(output.stderr);
        const json = await readTextFile(output.stdout.replace("\n", ""), {dir: BaseDirectory.Temp});
        console.log("json contents:", json);

        await removeFile(output.stdout.replace("\n", ""), {dir: BaseDirectory.Temp});
        
        const projectAndTimeline =
          ConvertResolveConnections.toResolveConnection(json);
        setCurrentProject(projectAndTimeline.projectName);

        if (projectAndTimeline.timelineName) {
          setCurrentTimeline(projectAndTimeline.timelineName);
        }
      } catch (error) {
        console.log(error);
      }
    };

    fetchProjectAndTimeline(); // Initial fetch
    intervalId = setInterval(fetchProjectAndTimeline, 5000); // Fetch every 5 seconds

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
