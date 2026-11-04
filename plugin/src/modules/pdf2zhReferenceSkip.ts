/** Capability negotiation for opt-in Reference Skip and older Servers. */
export function supportsReferenceSkip(payload: unknown): boolean {
    return (
        payload !== null &&
        typeof payload === "object" &&
        !Array.isArray(payload) &&
        "referenceSkip" in payload &&
        payload.referenceSkip === true
    );
}
