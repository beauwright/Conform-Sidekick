import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import { ResolveConnectionSchema } from "./jsonParse/ResolveConnections";
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
  children: ReactNode;
}

export const ResolveProvider = ({ children }: ResolveProviderProps) => {
  const [currentProject, setCurrentProject] = useState("");
  const [currentTimeline, setCurrentTimeline] = useState("");

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | null = null;
    const fetchProjectAndTimeline = async () => {
      try {
        const projectAndTimeline = await getObjectFromPythonSidecar(["projectAndTimeline"], ResolveConnectionSchema.parse)
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
    intervalId = setInterval(fetchProjectAndTimeline, 10000);
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
