import { z } from 'zod';

// Define the Zod schema for TempOutput
const TempOutputSchema = z.object({
    path: z.string(),
});

// TypeScript type derived from the Zod schema
export type TempOutput = z.infer<typeof TempOutputSchema>;