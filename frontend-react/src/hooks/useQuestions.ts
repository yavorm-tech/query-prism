import { useQuery } from "@tanstack/react-query";
import { qk } from "../lib/queryKeys";
import { getTopicQuestions } from "../lib/api/topics";

export function useQuestions(topicId: string) {
  return useQuery({
    queryKey: qk.questions(topicId),
    queryFn: () => getTopicQuestions(topicId),
    enabled: Boolean(topicId),
  });
}
