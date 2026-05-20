/** Friendly random reviewer names for anonymous share-link visitors who
 *  don't type their own name. Adjective + animal — recognizable, distinct
 *  enough across a handful of reviewers, never offensive. */

const ADJECTIVES = [
  "Curious", "Careful", "Sharp", "Patient", "Bright", "Keen", "Thoughtful",
  "Diligent", "Astute", "Precise", "Earnest", "Lucid", "Steady", "Candid",
  "Eager", "Measured", "Rigorous", "Attentive",
];

const ANIMALS = [
  "Otter", "Heron", "Falcon", "Badger", "Lynx", "Magpie", "Marmot",
  "Tern", "Wren", "Ibex", "Vole", "Finch", "Pika", "Stoat", "Crane",
  "Newt", "Shrew", "Hare",
];

/** e.g. "Curious Otter". */
export function randomReviewerName(): string {
  const a = ADJECTIVES[Math.floor(Math.random() * ADJECTIVES.length)];
  const n = ANIMALS[Math.floor(Math.random() * ANIMALS.length)];
  return `${a} ${n}`;
}
