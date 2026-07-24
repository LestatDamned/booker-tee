import { describe, expect, it } from "vitest";

import { importMappingPayload } from "./test-support";
import {
  assignMappingColumnRole,
  mappingRoleCanBeAssigned,
  mappingRoleForColumn,
} from "./mapping-draft";

describe("column mapping draft", () => {
  it("swaps roles when an occupied role is assigned to another column", () => {
    const command = importMappingPayload().defaultMapping;

    const changed = assignMappingColumnRole(command, 3, "descriptionColumn");

    expect(changed.descriptionColumn).toBe(3);
    expect(changed.balanceAfterColumn).toBe(1);
    expect(mappingRoleForColumn(changed, 1)).toBe("balanceAfterColumn");
  });

  it("allows an optional role to be removed", () => {
    const command = importMappingPayload().defaultMapping;

    const changed = assignMappingColumnRole(command, 3, null);

    expect(changed.balanceAfterColumn).toBeNull();
    expect(mappingRoleForColumn(changed, 3)).toBeNull();
  });

  it("keeps required roles assigned until they can be swapped", () => {
    const command = importMappingPayload().defaultMapping;

    expect(assignMappingColumnRole(command, 0, null)).toBe(command);
    expect(mappingRoleCanBeAssigned(command, 0, "postingDateColumn")).toBe(
      false,
    );
  });
});
