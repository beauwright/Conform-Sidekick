import { z } from 'zod';

export const ResolveConnectionSchema = z.object({
    projectName: z.string(),
    timelineName: z.string().optional(),
});

export type ResolveConnection = z.infer<typeof ResolveConnectionSchema>;