---
title: Native scope source
status: candidate
normative: true
stability: v1
updated: 2026-11-17
see_also:
  - ../conformance/normative-language.md
---

# 受限原生 scope 来源

## 1. 角色与唯一运输（normative）

`ak.peer.mls.read.native_scope_source.v1`（`POST /_arkret/peer/mls/native-scope-source/query`）只允许当前真实治理方G向exact Account/Agent固定owning Station H取得有限native资格来源。请求/响应形状唯一为[mls-native-scope-source.schema.json](../../artifacts/schemas/mls-native-scope-source.schema.json)；沿既有标准Service HTTP签名、same-core路由、完整Service方法历史、freshness与transport大小门，不产生私有RPC、通用对象fetch或新的身份。

G须从真实Realm authority chain/current取得exact `governance_authority_ref`，不能仅比较Service DID。G0→G1→G0后旧任期来源不属于新任期。H的角色固定于完整Account/Agent的Station，不能从DID托管域、kid、controller裸principal或Service调用者猜来源。RealmActor沿原已登记native claim/authority合同，不映射成Account，不由本操作扩大读取角色。

旧`ak.peer.keys.keypackages.read.claim.v1`仍是原requester的整批ledger查询，ACL/原首次结果/全数组receipt逐字保留；本来源不借其身份读其它requester或整批KeyPackages。`producer_agent_evidence`仍只适用于actual Agent producer，不变成Sidecar census。

请求由G自己构造。先走原caller/target资格和完整native业务结果probe；真实exact outcome命中仍返回原结果。只有miss才发fresh source query。不要将本source、query nonce或其它可替换current证据加入不可变Event/完整MLS业务identity；`ContentRecoverySource Some`的冻结业务身份不属于这个例外。

`purpose`封闭为mls_admission、sidecar_view、group_state_material、roster_authority、welcome_bootstrap、payload_delivery。后五者仅限Sidecar既有具名consumer；不是任意operation字符串或新内容权限。H只收到既有完整业务binding与本H的必要selected来源，不能因此看到整MLS单元、prejoin roster、其它Welcome/未入组KeyPackage、session secret或H私PCR。

## 2. 完整成员与永久fence basis（normative）

G先从真实native原件确定本次全部source-required完整Actor：原业务实际需要的creator/Add/retained origins，加Sidecar完整controller及候选B。不能由H正例/desired过滤后才决定targets，不能接受caller截短列表。

Sidecar候选B来自exact父Realm当前joined成员：原Agent join的完整controller绑定必须等于Sidecar owner且controller_membership_generation_ref等于controller当前join EventId。候选包含H侧paused/deactivated/无current runtime key等负例；不包含其它controller、其它Realm或H所有未入群Agent。完整member分类/required join来源缺失为unavailable，不当作排除证明。B字段顺序为sidecar_id、controller_account_id、sidecar_create_event_ref、controller_join_event_ref、candidate_joins；每个candidate字段为agent_actor_id、join_event_ref。候选按完整Actor的JCS UTF8 bytes排序，唯一Actor，原join EventId逐字保留。controller或Agent rejoin不能复活旧世代binding。

唯一私有`g_basis_preimage`字段顺序为domain、realm_id、effective_scope、governance_authority_ref、genesis_event_ref、sidecar_membership_basis、endpoint_fences；前者固定`ak.mls.native_scope_basis.v1`。genesis_event_ref只在G已有accepted MLS Genesis时存在；Sidecar basis只在Sidecar存在。字段缺席与null不同，禁止用null制造别名。整个原像为schema同名closed对象，`g_basis_digest = sha256(JCS(g_basis_preimage))`，沿现Hash格式。H只收到摘要和求值必要raw B，不收到私fence前像。

endpoint_fences精确为上述完整targets在exact scope/accepted Genesis的全部**已安装永久fence**。每行唯一投影为`{intent_digest,covered_authorizations}`，不能再加SQL id、时间、source_digest、challenge或leaf key。intent_digest必须从canonical first_source按content-history §10.1现I公式重算；原family、完整Actor/scope/genesis、source签名/接受资格和覆盖原件必须可独立核实或依法完整导入。只存I摘要/verified bool或缺失源不等于可用basis。

covered_authorizations为该行真实永久覆盖全集的`{actor_id,endpoint,authorization_event_ref}`三字段投影，按各完整对象的JCS UTF8 bytes排序去重；原永久predicate不比较MLS leaf key，同旧native authorization下换KeyPackage/key不能逃fence。行按intent_digest UTF8排序、唯一I。已安装且覆盖为空的行也必须保留，捕获first-fence birth；只有eligible/FailedPrecondition最小I而尚未安装fence的行排除。不能只从inventory.old_leaves、当前tree、正例pubkey或SQL max重建全集。fence永久保留，不因终局、缓存TTL或handoff删掉。

G在网络前捕获真实B/basis，释放本地事务后才求H。G末接纳/披露cut重算完整raw B及私fence basis：raw B须逐项相符，g_basis_digest亦须等于本地真实前像。不能拿opaque token代替raw B检查。源在途后G首次安装fence，即使旧claim从未入树/不在known endpoints，basis已改变，旧答复必须零效果拒绝。再次查询实际发生在G已知native恢复之后，H必须真实重评旧实例，不使用墙钟排序或H观察ledger。普通无关Message不改变此basis；不绑定whole Realm head。

## 3. 原件与endpoint实例（normative）

original_request_digest优先直接复用existing whole-native business hash。MLS Commit包含原Event/proof/approval Option与Vec顺序、inline bytes、全部Welcome、幂等键和冻结业务source，不得退成EventId。无现hash的Genesis/注册unit仅从原exact-original规则的完整carrier登记一次canonical binding，不改变ledger identity。H签其native条件用途，不宣称从opaque hash解析或验证了G的RFC内容；G仍持完整原件、重算binding并独立核全。

无existing binding的read/delivery仅登记一次closed原像：domain=`ak.mls.native_scope_use.v1`、purpose、caller_actor_id、existing_operation_request、target_originals、query_nonce_base64url。existing_operation_request是该具名consumer已有typed body/path selector的规范投影，不含认证token/任意header；target_originals只取本次实际准许的完整target ref/epoch/cut或exact batch原件。无原业务权限不构造该投影，不能用current空selector授权以后内容。已有效同像摘要直接复用。

ensure 与 MLS 规划是两个先后阶段：原 ensure.prepare 仅固定 create/context-attach drafts，原 ensure.commit 将它们原子接纳后才返回 key_material_pending。完整B的sidecar_create_event_ref必须来自该已接纳Create；不得把本操作提前塞入ensure.prepare。尚无accepted MLS Genesis的view/本地proposal规划可以在已接纳Sidecar上查询，genesis_event_ref缺席，endpoint_sources可为空；该来源只为该精确规划/读取用途，不授first admission。真正Genesis接纳另用原完整Genesis业务绑定及creator来源重查，不能把规划答复提升为准入证据。

endpoint_sources只有两个实际输入形状：first Add的{claim_id}（只复用既有closed query body形状，不借旧operation ACL），或creator/retained的{authorization_event_ref}单字段原件投影。后者两种业务角色由G自己的原件确定，不再复制kind/Actor/endpoint/key字段。

- first Add：H按claim_id查真实首次selected记录，核原intended Realm/scope/group与claim/admission/window，positive返回该唯一ContentEndpoint和原KeyPackage ref，不披露其它batch记录。G核实际Add/Welcome/RFC及selected关联。
- creator/retained：H只读自己真实accepted DeviceAuthorize或AgentKeyAuthorize原件；单Event的完整Actor及单一DeviceId或Agent VM已唯一决定native身份，须与其固定owning H、原accepted PCR和当前原生授权严格匹配。EventId本身不是访问凭据，原G角色、purpose、scope与隐私门仍必需。H仅回答该原authorization实例当前是否合格，不替G重验历史MLS leaf/key。
- G从完整原MlsGenesisCreatorLeafAuthority/producer/native source或durable Add consumed Proposal/Welcome/attestation原件独立取得exact ContentEndpoint，按actualRFC leaf核Actor、endpoint、authorization_ref和MLS key。native签名key与MLS leaf key可不同，但须原真实独立binding。不能从rawkey/当前key猜旧实例；同Actor/key A0→A1仍不同。creator不要求claim或尚不存在的retained tree；retained不因KeyPackage已过期而失效，不回传整旧source/Genesis/producerFact/晚attestation，避免递归B。

qualification.endpoint_qualifications严格等长、同序。授权EventId的positive只有{state:qualified}，不回显可由该原件唯一确定的Actor/endpoint或key；claim positive必须有现ContentEndpoint及原selected keypackage_ref。ineligible只表示真实核实negative；未知/损坏原native源整请求revision_unavailable，不冒负例。KPref由现owner对完整selected TLS bytes重算SHA256，不是UUID id或新同像digest。Sidecar返回与完整B.candidate_joins严格等长同序的boolean desired_qualifications；true只表示该exact候选native合格，false只表示真实negative，未知整请求不可用。G从被签raw B的true位置提取principal并UTF8排序去重，得到原desired_agent_ids，原五成员摘要公式不变。非Sidecar禁止该字段。controller不具current资格时不能以空desired伪装合法。

source-required endpoints由各原用途确定，不是返回对象中出现的所有历史leaf：Sidecar MLS接纳/ready核本次实际post-tree保留的端；普通Realm/Circle MLS仍只核原实际发送者、creator和本次first Add所需端，不将其它无关历史leaf全局current化。read、roster、group material、Welcome/bootstrap与payload batch核本次实际caller/recipient的current native实例和完整Sidecar B；响应里其它历史producer/leaf继续按原历史来源验证，不因其旧authorization不再current而否认合法历史读取，也不由此授予它们当前接收/发送权。各原target/floor/disclosure/consume/readiness门独立保留。

G将被签的原authorization EventId、claim positive的ContentEndpoint，与自己真实creator/Add/retained映射逐项核实，覆盖上述该用途实际需要的全部端；授权ref投影没有放松G原历史映射/RFC/key门。same Actor/key的A0→A1不能把旧leaf A0重新归属给A1。对Remove仅要求真实post-tree保留leaf当前合格，不要求将被移除旧leaf先合格。desired仍只表示native ownership/lifecycle/runtime-key与G membership，不包含target action、participation selection或readiness。

同一个原G业务可沿同一g_basis使用多次本操作：每份普通query均带原完整B（Sidecar）、exact原业务digest、fresh challenge与本次有限source投影，每份仍独立满足8MiB canonical/16MiB wire标准预算。G可以按实际bytes自然分配source集合，必要时每query只放一个authref或claim selector；不加batch_id/count/index/cursor，不把多份查询当新原子事务。G在末held cut必须按实际原件完整收齐全部必要source，核每份当前有效且g_basis相同，并重算raw B；不能漏行、把unknown当false或拼接截短B。多份Sidecar回答的desired_qualifications必须一致，不一致时本次原业务不可用并重新取得完整来源，不对不同集合取union。新original/read/batch仍独立fresh，不从旧source续租。

完整B的容量沿原parent Realm full-snapshot 8MiB最大披露预算，不新加成员写入否决：每个候选的canonical B row是完整Actor加92 bytes，同一Actor的最小current member row是Actor加290 bytes；含元素逗号分别+1。common did_core_id每项最多512码点，按最坏JSON转义6bytes/码点，完整Account Actor最多6213 bytes。因此候选数组的保守上界为(6306/6504)*8,388,608，尚留超过255,000 bytes给固定query字段与单selector；实际固定closed字段远小于此余量，单query始终可容纳完整B与一个必要selector。该证明不假定B在1MiB Event内。响应每候选boolean连逗号最多6bytes，成员最小row至少388bytes，故boolean数组少于130KiB；一个selected Endpoint受原单授权Event/原selected来源预算，且每query可只选一项，完整响应仍复测原8MiB。不得截短B、暗改64计数门、分块同cut或增加H观察表。

## 4. 唯一签名与接受截点（normative）

响应只有qualification、signature；请求已绑定的source/destination/scope/authority/nonce/original/basis不回显。唯一签名preimage为`UTF8("ak.mls.native_scope_source.v1\n") + JCS({request:exact_native_scope_source_request_body,qualification:qualification})`。source查询不包含响应/签名，无环，不新增同像request摘要。H使用标准Service Ed25519 KeyOperationSignature；kid只选H真实历史assertionMethod，不是producer Event方法，也不授路由。G独立验证并冻结完整H method-native Service历史、exact请求/响应和接受时间，不信裸公钥/verified标签。

issued_at<=now<expires_at；截止不得晚于原标准peer签名freshness/expiry允许的最早失效点、原native authorization窗口与本次first-claim实际截止。等待/锁后重核，不能让过期source进nonce/业务写。new query必须使用fresh CSPRNG32-byte canonical unpadded query nonce；原nonce/source不能给新original/read/batch续用。SDK pair verifier核scope/完整H/G身份/当前authorityRef、请求关联、结果长度/顺序/条件字段和时窗，schema通过不是授权。

§sidecar的F定义为本次**受限H source native cut + G实际cut的相关membership/永久fence/本地durable否定事实**。它不是H/G全局同时current或分布式事务。H在真实同源资格cut求值；G网络后在原同Realm/scope锁cut核真实current tenure、raw B、g_basis、base/RFC/provenance、controller/parent membership、AccountStatus/terminal、scope永久fence，以及原caller/session/ceiling/policy/capability/readiness/history门。

H后变更不全球召回已真实签发、未过期、同业务/挑战/audience/任期的exact在途原件。新original/query/delivery batch必须fresh challenge→实际H求值，旧source不是TTL lease。G自己已耐久的终态/AccountStatus、当前membership/tenure或永久fence始终占优；已安装新fence改变basis，旧在途答复也不能越过。此次不新增通用H观察ledger/PCR head数组，不以attested_at或不同opaque digest当可比revision。

## 5. 消费、历史与交接（normative）

View/desired、group material/握手、roster authority、Welcome引导、queued key/Welcome、payload/未来epoch材料及stream batch都在各自原current/target/disclosure门内使用此来源；不能只修forward提交。普通父Realm成员无Sidecar披露权，public RFC不等于公开读取。desired目标的exact Add/Welcome/claim lineage仍允许必要bootstrap，不提前要求effective；业务内容仍须原effective/consume/readiness。recipient H的实际交付session/current/原claim门独立保持。

first Add前新来源与真实consumed ordinal/selected Package/Welcome原关联，在G原接纳事务随Event/Commit/source依赖保管，供永久fence识别尚无晚attestation的Add。它不声称已消费或ready。原late attest_add只有真winning Commit/Welcome同replica cut后签，完整claim receipt验证、原签/方法闭包及outbox保留；缺它不回滚Commit，也不伪造历史roster。

真实完整原结果replay仍原样；probe miss/cold续跑不能只刷新Device证据而复用旧Sidecar source。合法G1激活前须实际导入本Realm该source、原accepted关联和永久fence/覆盖集合，H PCR/private keys不迁。新G当前查询取新任期source，旧audience不适用；原历史签名继续按其真实首次时点核。未知native源保持明确不可用，不以空表/当前tree/公开handoff链/缓存代完整保管。

纯schema/签名/摘要向量只证明其字节与闭值；不证明native参与账本、真实RFC、私库导入、物理交付或崩溃耐久。这些必须由实现owner真PG/网络/重启用例验证，不把命名suite或模拟布尔当生产证据。

`ak.vector.mls.native_scope_source.v1`只验证本合同的真实Ed25519/JCS与有限shape/关联拒绝；实际角色、完整G全集、原native来源及RFC/网络/耐久由独立审计承担。
