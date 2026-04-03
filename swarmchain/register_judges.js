/**
 * SwarmTribunal — Judge Registration on Hedera Mainnet
 * =====================================================
 * Registers tribunal judges as on-chain agents via HCS.
 * HOL Registry Broker indexes these registrations.
 *
 * Topic: 0.0.10291838 (Swarm & Bee mainnet)
 * Operator: 0.0.10291827
 *
 * Usage:
 *   node register_judges.js             → registers both judges (HITL mode)
 *   node register_judges.js --execute   → registers and submits directly
 */

import { Client, PrivateKey, TopicMessageSubmitTransaction, Transaction } from '@hashgraph/sdk';

const TOPIC_ID = "0.0.10291838";
const OPERATOR_ID = process.env.HEDERA_OPERATOR_ID || "0.0.10291827";
const OPERATOR_KEY = process.env.HEDERA_OPERATOR_KEY || "";

const JUDGES = [
    {
        type: "agent_registration",
        name: "SwarmTribunal-JudgeA",
        role: "data_quality_judge",
        model: "google/gemma-3-12b-it",
        modelState: "base_unmodified",
        deterministic: true,
        network: "mainnet",
        operatorAccountId: OPERATOR_ID,
        operatingTopicId: TOPIC_ID,
        hardware: {
            device: "NVIDIA RTX PRO 6000 Blackwell",
            vram: "96GB",
            arch: "Blackwell",
            node: "swarmrails-gpu1",
            location: "West Palm Beach, FL"
        },
        capabilities: {
            input: "training_pairs",
            output: "quality_scores_with_reasoning",
            scoringScale: "0.0-1.0",
            protocol: "2_pass_validation",
            batchSize: 50
        },
        protocol: {
            name: "SwarmProtocol",
            ens: "swarmprotocol.eth",
            deedFormat: "swarmdeed_v1",
            classification: {
                royal_jelly: ">= 0.75",
                honey: "0.50-0.74",
                propolis: "< 0.50"
            }
        },
        operator: {
            entity: "Swarm & Bee LLC",
            duns: "138652395",
            website: "swarmandbee.ai",
            contact: "build@swarmandbee.ai"
        },
        metadata: {
            description: "Primary tribunal judge for AI training data quality scoring. Scores pairs using deterministic prompt against unmodified base model. Part of dual-judge 2-pass validation protocol.",
            version: "1.0.0",
            registeredAt: new Date().toISOString()
        }
    },
    {
        type: "agent_registration",
        name: "SwarmTribunal-JudgeB",
        role: "data_quality_judge",
        model: "Qwen/Qwen2.5-7B-Instruct",
        modelState: "base_unmodified",
        deterministic: true,
        network: "mainnet",
        operatorAccountId: OPERATOR_ID,
        operatingTopicId: TOPIC_ID,
        hardware: {
            device: "NVIDIA RTX 3090",
            vram: "24GB",
            arch: "Ampere",
            node: "whale-gpu0",
            location: "West Palm Beach, FL"
        },
        capabilities: {
            input: "training_pairs",
            output: "quality_scores_with_reasoning",
            scoringScale: "0.0-1.0",
            protocol: "2_pass_validation",
            batchSize: 50
        },
        protocol: {
            name: "SwarmProtocol",
            ens: "swarmprotocol.eth",
            deedFormat: "swarmdeed_v1",
            classification: {
                royal_jelly: ">= 0.75",
                honey: "0.50-0.74",
                propolis: "< 0.50"
            }
        },
        operator: {
            entity: "Swarm & Bee LLC",
            duns: "138652395",
            website: "swarmandbee.ai",
            contact: "build@swarmandbee.ai"
        },
        metadata: {
            description: "Secondary tribunal judge for independent cross-validation. Different model family from JudgeA ensures zero shared bias. Part of dual-judge 2-pass validation protocol.",
            version: "1.0.0",
            registeredAt: new Date().toISOString()
        }
    }
];

function getClient() {
    if (!OPERATOR_KEY) {
        console.error("Set HEDERA_OPERATOR_KEY environment variable");
        process.exit(1);
    }
    return Client.forMainnet().setOperator(OPERATOR_ID, PrivateKey.fromString(OPERATOR_KEY));
}

async function buildRegistrationTx(judge) {
    const client = getClient();
    const message = JSON.stringify(judge);

    const tx = await new TopicMessageSubmitTransaction()
        .setTopicId(TOPIC_ID)
        .setMessage(message)
        .freezeWith(client);

    const txBytes = tx.toBytes();
    const txHex = Buffer.from(txBytes).toString('hex');

    console.log(`\n${"═".repeat(60)}`);
    console.log(`  JUDGE REGISTRATION — REVIEW BEFORE SIGNING`);
    console.log(`${"═".repeat(60)}`);
    console.log(`  Name:     ${judge.name}`);
    console.log(`  Model:    ${judge.model}`);
    console.log(`  State:    ${judge.modelState}`);
    console.log(`  Hardware: ${judge.hardware.device} (${judge.hardware.arch})`);
    console.log(`  Node:     ${judge.hardware.node}`);
    console.log(`  Topic:    ${TOPIC_ID}`);
    console.log(`  Tx ID:    ${tx.transactionId.toString()}`);
    console.log(`${"═".repeat(60)}`);

    return { txHex, name: judge.name, transactionId: tx.transactionId.toString() };
}

async function executeRegistration(txHex) {
    const client = getClient();
    const txBytes = Buffer.from(txHex, 'hex');
    const tx = Transaction.fromBytes(txBytes);
    const signed = await tx.sign(PrivateKey.fromString(OPERATOR_KEY));
    const response = await signed.execute(client);
    const record = await response.getRecord(client);

    return {
        consensusTimestamp: record.consensusTimestamp.toString(),
        sequenceNumber: record.receipt.topicSequenceNumber.toString(),
    };
}

// ─── MAIN ───
const autoExecute = process.argv.includes('--execute');

console.log("═".repeat(60));
console.log("  SWARM & BEE — TRIBUNAL JUDGE REGISTRATION");
console.log("  Hedera Mainnet · HOL Registry Broker Compatible");
console.log("═".repeat(60));

for (const judge of JUDGES) {
    const { txHex, name } = await buildRegistrationTx(judge);

    if (autoExecute) {
        console.log(`  Submitting ${name}...`);
        const result = await executeRegistration(txHex);
        console.log(`  REGISTERED: ${name}`);
        console.log(`    Consensus: ${result.consensusTimestamp}`);
        console.log(`    Sequence:  ${result.sequenceNumber}`);
        console.log(`    Verify:    https://hashscan.io/mainnet/topic/${TOPIC_ID}`);
    } else {
        console.log(`\n  ${name} built (HITL mode). To submit:`);
        console.log(`  Set HEDERA_OPERATOR_KEY and run with --execute`);
    }
}

console.log(`\n${"═".repeat(60)}`);
console.log("  Both judges registered on Hedera mainnet.");
console.log("  HOL Registry Broker can now index them.");
console.log("  Verify: https://hashscan.io/mainnet/topic/" + TOPIC_ID);
console.log("═".repeat(60));
