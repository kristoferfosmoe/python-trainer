// Tiny hash router: #/, #/lesson/<id>/<page>, #/playground/<challenge>.
// Hash URLs need no server configuration.

import { useEffect, useState } from "react";

export type Route =
  | { page: "map" }
  | { page: "signin" }
  | { page: "signup" }
  | { page: "account" }
  | { page: "lesson"; lessonId: string; pageNumber?: number }
  | { page: "playground"; challengeId?: string };

export function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "lesson" && parts[1]) {
    const pageNumber = Number(parts[2]);
    return { page: "lesson", lessonId: parts[1], pageNumber: Number.isInteger(pageNumber) && pageNumber > 0 ? pageNumber : undefined };
  }
  if (parts[0] === "playground") return { page: "playground", challengeId: parts[1] };
  if (parts[0] === "signin" || parts[0] === "signup" || parts[0] === "account") return { page: parts[0] };
  return { page: "map" };
}

export function href(route: Route): string {
  switch (route.page) {
    case "map":
      return "#/";
    case "signin":
    case "signup":
    case "account":
      return `#/${route.page}`;
    case "lesson":
      return `#/lesson/${encodeURIComponent(route.lessonId)}${route.pageNumber ? `/${route.pageNumber}` : ""}`;
    case "playground":
      return `#/playground${route.challengeId ? `/${encodeURIComponent(route.challengeId)}` : ""}`;
  }
}

export function navigate(route: Route) {
  window.location.hash = href(route);
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));
  useEffect(() => {
    const update = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}
