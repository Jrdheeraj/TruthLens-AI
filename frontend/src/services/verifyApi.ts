import { VerificationResponse } from "../types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

export const verifyText = async (text: string): Promise<VerificationResponse> => {
  const response = await fetch(`${API_BASE_URL}/verify/text`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to verify text");
  }

  return response.json();
};

export const verifyImage = async (file: File): Promise<VerificationResponse> => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/verify/image`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to verify image");
  }

  return response.json();
};

export const verifyVideo = async (file: File): Promise<VerificationResponse> => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/verify/video`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to verify video");
  }

  return response.json();
};

export const verifyMultimodal = async (text: string, file?: File): Promise<VerificationResponse> => {
  const formData = new FormData();
  if (text) formData.append("text", text);
  if (file) formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/verify/multimodal`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to verify multimodal content");
  }

  return response.json();
};
