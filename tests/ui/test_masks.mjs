import assert from 'node:assert/strict';
import {formatMask} from '../../src/oficina/ui/masked_input.js';

assert.equal(formatMask('52998224725', 'cpf'), '529.982.247-25');
assert.equal(formatMask('529.982.247-25', 'cpf'), '529.982.247-25');
assert.equal(formatMask('abc52998', 'cpf'), '529.98');
assert.equal(formatMask('11987654321', 'phone'), '(11) 98765-4321');
assert.equal(formatMask('1134567890', 'phone'), '(11) 3456-7890');
assert.equal(formatMask('', 'phone'), '');
assert.equal(formatMask('11', 'phone'), '(11');
assert.equal(formatMask('529982247259999', 'cpf'), '529.982.247-25');
console.log('8 verificações de máscaras aprovadas.');
