const MAX_PHOTO_BYTES = 10 * 1024 * 1024;
const acceptedTypes = new Set(["image/jpeg", "image/png", "image/webp"]);

export type PhotoInspection = {width: number; height: number; warnings: string[]};

export function validatePhotoFile(file: Pick<File, "size" | "type">): void {
  if (!acceptedTypes.has(file.type)) throw new Error("Choose a JPG, PNG, or WebP image.");
  if (file.size === 0) throw new Error("This file is empty. Choose a photo that opens on your device.");
  if (file.size > MAX_PHOTO_BYTES) throw new Error("The image exceeds the 10 MB upload limit. Choose a smaller file.");
}

export function photoQualityWarnings(width: number, height: number, averageBrightness: number | null, visualDetail: number | null = null): string[] {
  const warnings: string[] = [];
  if (Math.min(width, height) < 480) warnings.push("The photo is low-resolution. Try a closer, sharper image if the AI misses details.");
  if (averageBrightness !== null && averageBrightness < 39) warnings.push("The photo appears very dark. Add lighting before scanning for better visibility.");
  if (averageBrightness !== null && averageBrightness > 242) warnings.push("The photo appears very bright or washed out. Reduce glare and try again.");
  if (visualDetail !== null && visualDetail < 2 && averageBrightness !== null && averageBrightness >= 39 && averageBrightness <= 242) {
    warnings.push("Very little visual detail is visible. The photo may be out of focus, obscured, or mostly blank; try another angle.");
  }
  return warnings;
}

export async function inspectHouseholdPhoto(file: File): Promise<PhotoInspection> {
  validatePhotoFile(file);
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new Error("This image couldn't be opened. It may be damaged or encoded in an unsupported format.");
  }
  try {
    const {width, height} = bitmap;
    if (width < 1 || height < 1) throw new Error("This photo has invalid dimensions.");
    const canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 64;
    const context = canvas.getContext("2d", {willReadFrequently: true});
    let brightness: number | null = null;
    let visualDetail: number | null = null;
    if (context) {
      context.drawImage(bitmap, 0, 0, 64, 64);
      const pixels = context.getImageData(0, 0, 64, 64).data;
      let total = 0;
      let count = 0;
      let edgeTotal = 0;
      let edgeCount = 0;
      const luminance = new Float32Array(64 * 64);
      for (let i = 0; i < pixels.length; i += 4) {
        if (pixels[i + 3] < 200) continue;
        const value = pixels[i] * 0.2126 + pixels[i + 1] * 0.7152 + pixels[i + 2] * 0.0722;
        total += value;
        luminance[i / 4] = value;
        count++;
      }
      if (count) brightness = total / count;
      for (let y = 1; y < 63; y++) {
        for (let x = 1; x < 63; x++) {
          const i = y * 64 + x;
          edgeTotal += Math.abs(4 * luminance[i] - luminance[i - 1] - luminance[i + 1] - luminance[i - 64] - luminance[i + 64]);
          edgeCount++;
        }
      }
      if (edgeCount) visualDetail = edgeTotal / edgeCount;
    }
    return {width, height, warnings: photoQualityWarnings(width, height, brightness, visualDetail)};
  } finally {
    bitmap.close();
  }
}
