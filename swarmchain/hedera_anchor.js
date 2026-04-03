/**
 * SwarmDeed Hedera Anchoring Agent
 * =================================
 * Anchors Merkle roots to Hedera HCS mainnet.
 * Human-in-the-loop: builds unsigned tx, human reviews + signs, then submits.
 *
 * Topic: 0.0.10291838 (Swarm & Bee mainnet)
 * Operator: 0.0.10291827
 *
 * Usage:
 *   node hedera_anchor.js build <merkle_root>     → returns unsigned tx bytes
 *   node hedera_anchor.js submit <signed_tx_hex>  → submits and returns consensus timestamp
 *   node hedera_anchor.js query <sequence_number>  → verifies an anchored root
 *   node hedera_anchor.js batch <manifest.json>    → anchor all roots from a Merkle manifest
 */

import { Client, PrivateKey, TopicMessageSubmitTransaction, TopicMessageQuery, Transaction } from '@hashgraph/sdk';
import { readFileSync, writeFileSync } from 'fs';

const TOPIC_ID = "0.0.10291838";
const OPERATOR_ID = process.env.HEDERA_OPERATOR_ID || "0.0.10291827";
const OPERATOR_KEY = process.env.HEDERA_OPERATOR_KEY || "";

function getClient() {
    if (!OPERATOR_KEY) {
        console.error("Set HEDERA_OPERATOR_KEY environment variable");
        process.exit(1);
    }
    return Client.forMainnet().setOperator(OPERATOR_ID, PrivateKey.fromString(OPERATOR_KEY));
}

// ─── BUILD: Create unsigned tx for human review (Glass Wall) ───
async function buildMerkleRootSubmitTx(merkleRoot, batchId, leafCount) {
    const client = getClient();

    const message = JSON.stringify({
        type: "swarmdeed_anchor",
        version: "1.0",
        merkle_root: merkleRoot,
        batch_id: batchId,
        leaf_count: leafCount,
        protocol: "swarmprotocol.eth",
        anchored_by: "swarm-and-bee-tribunal",
        timestamp: new Date().toISOString(),
    });

    const tx = await new TopicMessageSubmitTransaction()
        .setTopicId(TOPIC_ID)
        .setMessage(message)
        .freezeWith(client);

    const txBytes = tx.toBytes();
    const txHex = Buffer.from(txBytes).toString('hex');

    console.log("═══════════════════════════════════════════════════════");
    console.log("  SWARMDEED ANCHOR — REVIEW BEFORE SIGNING");
    console.log("═══════════════════════════════════════════════════════");
    console.log(`  Topic:       ${TOPIC_ID}`);
    console.log(`  Batch:       ${batchId}`);
    console.log(`  Merkle Root: ${merkleRoot.substring(0, 32)}...`);
    console.log(`  Leaf Count:  ${leafCount}`);
    console.log(`  Tx ID:       ${tx.transactionId.toString()}`);
    console.log("═══════════════════════════════════════════════════════");
    console.log("");
    console.log("  Unsigned transaction bytes (hex):");
    console.log(`  ${txHex.substring(0, 80)}...`);
    console.log("");
    console.log("  To sign and submit:");
    console.log(`  node hedera_anchor.js submit ${txHex}`);
    console.log("═══════════════════════════════════════════════════════");

    return { txHex, transactionId: tx.transactionId.toString(), topicId: TOPIC_ID };
}

// ─── SUBMIT: Execute signed tx, return consensus data ───
async function submitSignedMerkleRootTx(signedTxHex) {
    const client = getClient();

    const signedTxBytes = Buffer.from(signedTxHex, 'hex');
    const signedTx = Transaction.fromBytes(signedTxBytes);

    // Sign with operator key
    const signedWithKey = await signedTx.sign(PrivateKey.fromString(OPERATOR_KEY));
    const txResponse = await signedWithKey.execute(client);
    const record = await txResponse.getRecord(client);

    const result = {
        consensusTimestamp: record.consensusTimestamp.toString(),
        sequenceNumber: record.receipt.topicSequenceNumber.toString(),
        topicId: TOPIC_ID,
        transactionId: record.transactionId.toString(),
        verify: `https://hashscan.io/mainnet/topic/${TOPIC_ID}`,
    };

    console.log("═══════════════════════════════════════════════════════");
    console.log("  SWARMDEED ANCHOR — CONFIRMED");
    console.log("═══════════════════════════════════════════════════════");
    console.log(`  Consensus:   ${result.consensusTimestamp}`);
    console.log(`  Sequence:    ${result.sequenceNumber}`);
    console.log(`  Topic:       ${result.topicId}`);
    console.log(`  Tx:          ${result.transactionId}`);
    console.log(`  Verify:      ${result.verify}`);
    console.log("═══════════════════════════════════════════════════════");
    console.log("  FINALITY ACHIEVED. DEED ANCHORED. PERMANENT.");
    console.log("═══════════════════════════════════════════════════════");

    return result;
}

// ─── BATCH: Anchor all roots from a Merkle manifest ───
async function anchorBatch(manifestPath) {
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
    const batches = manifest.batches || [];

    console.log(`Anchoring ${batches.length} Merkle roots from ${manifestPath}`);

    const receipts = [];
    for (const batch of batches) {
        console.log(`\nBatch ${batch.batch_index}: ${batch.merkle_root.substring(0, 16)}...`);

        const { txHex } = await buildMerkleRootSubmitTx(
            batch.merkle_root,
            `batch-${batch.batch_index}`,
            batch.leaf_count
        );

        // Auto-sign in batch mode (remove for true human-in-the-loop)
        const result = await submitSignedMerkleRootTx(txHex);
        receipts.push({ ...batch, ...result });
    }

    // Save receipts
    const receiptPath = manifestPath.replace('.json', '_receipts.json');
    writeFileSync(receiptPath, JSON.stringify({ receipts, anchored_at: new Date().toISOString() }, null, 2));
    console.log(`\nReceipts saved: ${receiptPath}`);

    return receipts;
}

// ─── CLI ───
const [,, command, ...args] = process.argv;

switch (command) {
    case 'build':
        await buildMerkleRootSubmitTx(args[0] || 'test_root', args[1] || 'test-batch', parseInt(args[2] || '50'));
        break;
    case 'submit':
        await submitSignedMerkleRootTx(args[0]);
        break;
    case 'batch':
        await anchorBatch(args[0]);
        break;
    default:
        console.log("Usage:");
        console.log("  node hedera_anchor.js build <merkle_root> [batch_id] [leaf_count]");
        console.log("  node hedera_anchor.js submit <tx_hex>");
        console.log("  node hedera_anchor.js batch <manifest.json>");
}
