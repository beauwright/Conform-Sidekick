import { z } from 'zod';

export const ConversionResultSchema = z.object({
    error_message: z.string().optional(),
    file_path: z.string().optional(),
    success: z.boolean(),
});

export type ConversionResult = z.infer<typeof ConversionResultSchema>;