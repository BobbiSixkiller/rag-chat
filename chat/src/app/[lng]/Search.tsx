"use client";

import { useParams } from "next/navigation";
import { useState } from "react";

const SearchComponent = () => {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState("");
  const { lng } = useParams<{ lng: string }>();

  const fetchAndStream = async () => {
    const res = await fetch(
      `http://vector-embed:8000/search?query=${encodeURIComponent(
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
    <div>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search query"
        className="border shadow-sm p-2"
      />
      <button
        onClick={handleSearch}
        className="cursor-pointer border bg-blue-300 p-2"
      >
        Search
      </button>

      <div>
        <h3>Response:</h3>
        <pre>{response}</pre>
      </div>
    </div>
  );
};

export default SearchComponent;
