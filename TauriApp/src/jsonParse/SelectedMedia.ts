import { z } from 'zod';

const ClipSchema = z.object({
    timecode: z.string(),
    track: z.number()
});

const SelectedMediaElementSchema = z.object({
    displayName: z.string(),
    binLocation: z.string(),
    resolution: z.string(),
    clips: z.array(ClipSchema),
    filepath: z.string(),
    mediaId: z.string(),
    clipType: z.string(),
    fieldType: z.string(),
    status: z.string().default("Unconverted"),
    statusMessage: z.string().default("This file has not been converted.")
});

export const SelectedMediaSchema = z.object({
    scope: z.string(),
    selectedMedia: z.array(SelectedMediaElementSchema)
});

export type SelectedMedia = z.infer<typeof SelectedMediaSchema>;
export type SelectedMediaElement = z.infer<typeof SelectedMediaElementSchema>;
export type Clip = z.infer<typeof ClipSchema>;
