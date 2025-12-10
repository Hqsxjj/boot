
// Simple wrapper for backend API calls

export const api = {
  get: async (url: string) => {
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`API Error: ${res.status}`);
      return await res.json();
    } catch (e) {
      console.error("API Get Error", e);
      return null;
    }
  },

  post: async (url: string, data: any) => {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (!res.ok) throw new Error(`API Error: ${res.status}`);
      return await res.json();
    } catch (e) {
      console.error("API Post Error", e);
      return null;
    }
  }
};
