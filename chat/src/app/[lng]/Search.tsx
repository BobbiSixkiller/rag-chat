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
    const res = await fetch(
      `http://localhost:8000/search?query=${encodeURIComponent(
        query
      )}&language=${lng}`
    );
    const reader = res?.body?.getReader();
    const decoder = new TextDecoder();
    let result = "";

    while (true) {
      const stream = await reader?.read();
      if (stream?.done) break;

      result += decoder.decode(stream?.value, { stream: true });
      setResponse(result); // Update the response progressively
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

      <div className="">
        <h3>Response:</h3>
        <pre>{response}</pre>
      </div>
    </div>
  );
};

export default SearchComponent;
