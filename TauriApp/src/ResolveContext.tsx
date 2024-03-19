import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
//import { Convert as ConvertOddPhotos, OddResMedia } from "./jsonParse/OddPhotos";
import { Convert as ConvertResolveConnections } from "./jsonParse/ResolveConnections";
import { getObjectFromPythonSidecar } from "./lib/utils";

interface ResolveContextType {
  currentProject: string;
  currentTimeline: string;
}

const ResolveContext = createContext<ResolveContextType | null>(null);

export const useResolveContext = () => {
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
        const projectAndTimeline = await getObjectFromPythonSidecar(["projectAndTimeline"], ConvertResolveConnections.toResolveConnection)
        
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
    //intervalId = setInterval(fetchProjectAndTimeline, 20000); // Fetch every 4 seconds

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
