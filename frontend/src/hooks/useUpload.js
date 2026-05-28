import { useState } from "react";
import { uploadFile } from "../services/ingestionService";

export function useUpload() {
  const [status, setStatus] = useState("idle"); // idle | uploading | success | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function upload(file, sourceType) {
    setStatus("uploading");
    setError(null);
    setResult(null);
    try {
      const data = await uploadFile(file, sourceType);
      setResult(data);
      setStatus("success");
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed.");
      setStatus("error");
    }
  }

  function reset() {
    setStatus("idle");
    setResult(null);
    setError(null);
  }

  return { upload, status, result, error, reset };
}
