import { useState, useRef } from "react";
import { useUpload } from "../hooks/useUpload";
import { SOURCE_TYPES } from "../utils/constants";

export default function UploadPage() {
  const { upload, status, result, error, reset } = useUpload();
  const [sourceType, setSourceType] = useState(SOURCE_TYPES[0].value);
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef();

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!file) return;
    await upload(file, sourceType);
  }

  if (status === "success") {
    return (
      <div className="max-w-lg space-y-4">
        <div className="bg-green-50 border border-green-200 rounded-lg p-5">
          <p className="font-medium text-green-800">Upload complete</p>
          <div className="mt-2 text-sm text-green-700 space-y-1">
            <p>Total rows: <strong>{result.total_rows}</strong></p>
            <p>Valid: <strong>{result.valid_rows}</strong></p>
            <p>Flagged for review: <strong>{result.flagged_rows}</strong></p>
            <p>Failed to parse: <strong>{result.failed_rows}</strong></p>
          </div>
        </div>
        <button
          onClick={reset}
          className="text-sm text-brand-600 hover:underline"
        >
          Upload another file
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-lg space-y-6">
      <h2 className="text-lg font-semibold text-gray-900">Upload data</h2>
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Data source type
          </label>
          <select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-600"
          >
            {SOURCE_TYPES.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            File (CSV)
          </label>
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg px-6 py-10 text-center cursor-pointer transition-colors ${
              dragOver ? "border-brand-600 bg-brand-50" : "border-gray-300 hover:border-gray-400"
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => setFile(e.target.files[0])}
            />
            {file ? (
              <p className="text-sm text-gray-700 font-medium">{file.name}</p>
            ) : (
              <p className="text-sm text-gray-400">
                Drop a CSV here or <span className="text-brand-600">browse</span>
              </p>
            )}
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={!file || status === "uploading"}
          className="w-full bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium py-2 rounded transition-colors disabled:opacity-50"
        >
          {status === "uploading" ? "Processing…" : "Upload and process"}
        </button>
      </form>
    </div>
  );
}
