/** Capability negotiation for the opt-in math compatibility pass. */
export function supportsMathCompatibility(payload: unknown): boolean {
    return (
        payload !== null &&
        typeof payload === "object" &&
        !Array.isArray(payload) &&
        "mathCompatibility" in payload &&
        payload.mathCompatibility === true
    );
}
