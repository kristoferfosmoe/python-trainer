import { describe, expect, it } from "vitest";
import { href, parseRoute } from "./router";

describe("parseRoute", () => {
  it("reads every kind of page", () => {
    expect(parseRoute("#/")).toEqual({ page: "map" });
    expect(parseRoute("#/lesson/for-loops/3")).toEqual({ page: "lesson", lessonId: "for-loops", pageNumber: 3 });
    expect(parseRoute("#/playground/first-drive")).toEqual({ page: "playground", challengeId: "first-drive" });
    expect(parseRoute("#/teams/4/Brave%20Otter")).toEqual({ page: "member", teamId: 4, username: "Brave Otter" });
  });

  it("keeps a broken %-escape as typed instead of crashing", () => {
    expect(() => decodeURIComponent("%E0%A4%A")).toThrow(URIError);
    expect(parseRoute("#/lesson/%E0%A4%A")).toEqual({ page: "lesson", lessonId: "%E0%A4%A", pageNumber: undefined });
    expect(parseRoute("#/teams/4/%zz")).toEqual({ page: "member", teamId: 4, username: "%zz" });
    expect(parseRoute("#/%")).toEqual({ page: "map" });
  });

  it("reads back what href writes", () => {
    const route = { page: "member", teamId: 7, username: "Kid/With%Odd name" } as const;
    expect(parseRoute(href(route))).toEqual(route);
  });
});
