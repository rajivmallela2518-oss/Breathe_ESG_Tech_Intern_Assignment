import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useUpload } from "../hooks/useUpload";
import { SOURCE_TYPES } from "../utils/constants";

export default function UploadPage() {
  const navigate = useNavigate();
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
    const hasFlags = result.flagged_rows > 0 || result.failed_rows > 0;
    return (
      <div className="max-w-lg space-y-4">
        <div className="bg-green-50 border border-green-200 rounded-lg p-5">
          <p className="font-medium text-green-800 mb-3">Upload complete</p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
            <span className="text-green-700">Total rows</span>
            <span className="font-semibold text-green-900">{result.total_rows}</span>
            <span className="text-green-700">Valid</span>
            <span className="font-semibold text-green-900">{result.valid_rows}</span>
            <span className="text-green-700">Flagged for review</span>
            <span className={`font-semibold ${result.flagged_rows > 0 ? "text-yellow-700" : "text-green-900"}`}>
              {result.flagged_rows}
            </span>
            <span className="text-green-700">Failed to parse</span>
            <span className={`font-semibold ${result.failed_rows > 0 ? "text-red-700" : "text-green-900"}`}>
              {result.failed_rows}
            </span>
          </div>
        </div>

        {hasFlags && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 text-sm text-yellow-800">
            {result.flagged_rows} row{result.flagged_rows !== 1 ? "s" : ""} need analyst review before they can be approved.
          </div>
        )}

        <div className="flex gap-4 pt-1">
          <button
            onClick={() => navigate("/review")}
            className="bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2 rounded transition-colors"
          >
            Go to review queue →
          </button>
          <button
            onClick={reset}
            className="text-sm text-gray-500 hover:text-gray-800 transition-colors"
          >
            Upload another file
          </button>
        </div>
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
