"use client";

import { useTranslation } from "@/lib/i18n/client";
import { useParams } from "next/navigation";
import { useState } from "react";

const SearchComponent = () => {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState("");
  const { lng } = useParams<{ lng: string }>();

  const { t } = useTranslation(lng, "search");

  const fetchAndStream = async () => {
    try {
      const res = await fetch(
        `http://localhost:8000/search?query=${encodeURIComponent(
          query
        )}&language=${lng}`
      );
      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let result = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        try {
          console.log(chunk);
          const parsed = JSON.parse(chunk);
          result += parsed.response;
          setResponse(result); // Update the response progressively
        } catch (err) {
          console.error("Error parsing chunk:", err);
        }
      }
    } catch (err) {
      console.error("Streaming error:", err);
    }
  };

  const handleSearch = () => {
    setResponse(""); // Reset the response before starting the search
    fetchAndStream();
  };

  return (
    <div className="w-xl">
      <div className="flex gap-2 pb-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search query"
          className="border shadow-sm w-full p-2 mr-2"
        />
        <button
          onClick={handleSearch}
          className="cursor-pointer border bg-green-300 p-2"
        >
          {t("submit")}
        </button>
      </div>

      <div className="max-w-xl flex flex-col gap-1">
        <h3>Response:</h3>
        <p>{response}</p>
      </div>
    </div>
  );
};

export default SearchComponent;
