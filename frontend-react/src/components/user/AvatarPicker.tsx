import { useState, useRef } from "react";
import { Loader2 } from "lucide-react";
import { uploadAvatar, deleteAvatar } from "../../lib/api/auth";
import { useAuth } from "../../lib/auth-context";

interface Props {
  initials: string;
}

const MAX_BYTES = 1024 * 1024; // 1 MB

async function compressToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(objectUrl);
      const canvas = document.createElement("canvas");
      let { width, height } = img;
      const MAX_DIM = 1024;
      if (width > MAX_DIM || height > MAX_DIM) {
        const scale = MAX_DIM / Math.max(width, height);
        width = Math.round(width * scale);
        height = Math.round(height * scale);
      }
      canvas.width = width;
      canvas.height = height;
      canvas.getContext("2d")!.drawImage(img, 0, 0, width, height);
      let quality = 0.85;
      let dataUrl = canvas.toDataURL("image/jpeg", quality);
      while (dataUrl.length * 0.75 > MAX_BYTES && quality > 0.1) {
        quality = Math.round((quality - 0.1) * 10) / 10;
        dataUrl = canvas.toDataURL("image/jpeg", quality);
      }
      resolve(dataUrl);
    };
    img.onerror = reject;
    img.src = objectUrl;
  });
}

export default function AvatarPicker({ initials }: Props) {
  const { user, refreshUser } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";

    setError(null);
    setWarning(null);

    let dataUrl: string;
    if (file.size > MAX_BYTES) {
      setWarning("Image too large — compressing automatically.");
      try {
        dataUrl = await compressToDataUrl(file);
      } catch {
        setError("Failed to compress image.");
        return;
      }
    } else {
      dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (ev) => resolve(ev.target?.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
    }

    setUploading(true);
    try {
      await uploadAvatar(dataUrl);
      await refreshUser();
      setWarning(null);
    } catch {
      setError("Failed to save avatar. Please try again.");
    } finally {
      setUploading(false);
    }
  }

  async function handleRemove() {
    setError(null);
    setUploading(true);
    try {
      await deleteAvatar();
      await refreshUser();
    } catch {
      setError("Failed to remove avatar.");
    } finally {
      setUploading(false);
    }
  }

  const avatarUrl = user?.avatar ?? null;

  return (
    <div className="flex items-center gap-4">
      <button
        type="button"
        aria-label="Change avatar"
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        className="relative w-16 h-16 rounded-full overflow-hidden border-2 border-border hover:border-accent transition-colors focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-60"
      >
        {avatarUrl ? (
          <img src={avatarUrl} alt="Your avatar" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full bg-accent flex items-center justify-center text-white text-xl font-semibold">
            {initials}
          </div>
        )}
        {uploading && (
          <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
            <Loader2 size={20} className="text-white animate-spin" />
          </div>
        )}
      </button>

      <div className="space-y-1">
        <p className="text-sm font-medium">Profile picture</p>
        <p className="text-xs text-text-dim">Click your avatar to upload · Max 1 MB</p>
        {warning && <p className="text-xs text-amber-400">{warning}</p>}
        {error && <p className="text-xs text-red-400">{error}</p>}
        {avatarUrl && !uploading && (
          <button
            type="button"
            onClick={handleRemove}
            className="text-xs text-text-dim hover:text-red-400 transition-colors"
          >
            Remove picture
          </button>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFileChange}
        aria-label="Upload avatar image"
      />
    </div>
  );
}
