# start to write student model, hope to complete it in serval hours
import numpy as np
import tensorflow as tf
from tensorflow.models.rnn import rnn_cell
import time
import csv
from random import shuffle
import random
from tensorflow.models.rnn import rnn
from sklearn.metrics import mean_squared_error
from sklearn import metrics
from math import sqrt

class StudentModel(object):

    def __init__(self, is_training, config):
        self.batch_size = batch_size = config.batch_size
        self.num_steps = num_steps = config.num_steps
        self.num_skills = num_skills = config.num_skills
        self.hidden_size = config.hidden_size
        size = config.hidden_size
        input_size = config.input_size

        inputs = self._input_data = tf.placeholder(tf.int32, [batch_size])
        self._target_id = target_id = tf.placeholder(tf.int32, [batch_size])
        self._target_correctness = target_correctness = tf.placeholder(tf.float32, [batch_size])

        lstm_cell = rnn_cell.BasicLSTMCell(size, forget_bias = 0.1)

        if is_training and config.keep_prob < 1:
            lstm_cell = rnn_cell.DropoutWrapper(lstm_cell, output_keep_prob=config.keep_prob)

        cell = rnn_cell.MultiRNNCell([lstm_cell] * config.num_layers)

        self._initial_state = cell.zero_state(batch_size, tf.float32)

        with tf.device("/cpu:0"):
            labels = tf.expand_dims(self._input_data, 1)
            indices = tf.expand_dims(tf.range(0, batch_size, 1), 1)
            concated = tf.concat(1, [indices, labels])
            inputs = tf.sparse_to_dense(concated, tf.pack([batch_size, num_skills*2+1]), 1.0, 0.0)
            inputs.set_shape([batch_size, num_skills*2+1])
        #print inputs.get_shape()
        if is_training and config.keep_prob < 1:
            inputs = tf.nn.dropout(inputs, config.keep_prob)

        outputs = []
        states = []
        state = self._initial_state
        #inputs = tf.split(1, 1, inputs)
        with tf.variable_scope("RNN"):
            #tf.get_variable_scope().reuse_variables()
            #outputs, states = rnn.rnn(cell, inputs, initial_state=self._initial_state)
            (cell_output, state) = cell(inputs, state)
            #outputs = cell_output
            self._final_state = self._initial_state = state

        #output = outputs[-1]
        softmax_w = tf.get_variable("softmax_w", [size, num_skills])
        softmax_b = tf.get_variable("softmax_b", [num_skills])
        logits = tf.sigmoid(tf.matmul(cell_output, softmax_w) + softmax_b)

        logits = tf.reshape(logits, [-1])
        self._pred_values = pred_values = []
        for i in range(batch_size):
            #print logits[i][self._targets[i][0]]
            target_num = self._target_id[i]
            pred_values.append(tf.slice(logits, tf.add([i*batch_size],target_num), [1]))

        #pred_values = self._pred = tf.reshape(tf.concat(0, pred_values), [-1, batch_size])
        pred_values = self._pred = tf.reshape(tf.concat(0, pred_values), [batch_size])
        loss = -tf.reduce_sum(target_correctness*tf.log(pred_values)+(1-target_correctness)*tf.log(1-pred_values))


        self._cost = cost = tf.reduce_mean(loss)

        if not is_training:
            return

        self._lr = tf.Variable(0.0, trainable=False)
        tvars = tf.trainable_variables()

        grads, _ = tf.clip_by_global_norm(tf.gradients(cost, tvars), config.max_grad_norm)
        optimizer = tf.train.GradientDescentOptimizer(self.lr)
        self._train_op = optimizer.apply_gradients(zip(grads, tvars))

    def assign_lr(self, session, lr_value):
        session.run(tf.assign(self._lr, lr_value))

    @property
    def input_data(self):
        return self._input_data

    @property
    def auc(self):
        return self._auc

    @property
    def pred(self):
        return self._pred

    @property
    def target_id(self):
        return self._target_id

    @property
    def target_correctness(self):
        return self._target_correctness

    @property
    def initial_state(self):
        return self._initial_state

    @property
    def pred_values(self):
        return self._pred_values

    @property
    def cost(self):
        return self._cost

    @property
    def final_state(self):
        return self._final_state

    @property
    def lr(self):
        return self._lr

    @property
    def train_op(self):
        return self._train_op




class SmallConfig(object):
  """Small config."""
  init_scale = 0.1
  learning_rate = 0.7
  max_grad_norm = 5
  num_layers = 1
  num_steps = 1
  hidden_size = 300
  max_epoch = 4
  max_max_epoch = 20
  keep_prob = 1.0
  lr_decay = 0.7
  batch_size = 100
  num_skills = 100
  input_size = 20


def run_epoch(session, m, fileName, eval_op, verbose=False):
    """Runs the model on the given data."""
    #epoch_size = ((len(data) // m.batch_size) - 1) // m.num_steps
    start_time = time.time()
    costs = 0.0
    iters = 0
    #state = m.initial_state
    state = tf.zeros([m.batch_size, m.hidden_size])
    inputs, targets = read_data_from_csv_file(fileName)
    index = 0
    pred_labels = []
    actual_labels = []
    while(index+m.batch_size < len(inputs)):
        x = inputs[index:index+m.batch_size]
        y = targets[index:index+m.batch_size]
        target_id = []
        target_correctness = []
        for item in y:
            target_id.append(item[0])
            target_correctness.append(item[1])
            actual_labels.append(item[1])

        index += m.batch_size
        #print x

        cost, pred, state, _ = session.run([m.cost, m.pred, m.initial_state, eval_op], feed_dict={
            m.input_data: x,m.target_id: target_id,
            m.target_correctness: target_correctness})
        costs += cost
        iters += 1

        for p in pred:
            pred_labels.append(p)

        #if verbose and iters % 20 == 0:
        #    print("%.3f perplexity: %.3f speed: %.0f wps" % (iters * 1.0 / epoch_size, np.exp(costs / iters), iters * m.batch_size / (time.time() - start_time)))
    #print pred_labels
    rmse = sqrt(mean_squared_error(actual_labels, pred_labels))
    fpr, tpr, thresholds = metrics.roc_curve(actual_labels, pred_labels, pos_label=1)
    auc = metrics.auc(fpr, tpr)

    return rmse, auc

def read_data_from_csv_file(fileName):
    inputs = []
    targets = []
    rows = []
    skills_num = 100
    with open(fileName, "rb") as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        for row in reader:
            rows.append(row)
    index = 0
    i = 0
    print "the number of rows is " + str(len(rows))
    tuple_rows = []
    #turn list to tuple
    while(index < len(rows)-1):
        problems_num = int(rows[index][0])
        if(problems_num <= 2):
            index += 3
        else:
            tup = (rows[index], rows[index+1], rows[index+2])
            tuple_rows.append(tup)
            index += 3
    #shuffle the tuple

    random.shuffle(tuple_rows)
    print "The number of students is ", len(tuple_rows)
    while(i < len(tuple_rows)):
        #skip the num is smaller than 2
        tup = tuple_rows[i]
        problems_num = int(tup[0][0])
        if(problems_num <= 2):
            i += 1
        else:
            problem_ids = tup[1]
            correctness = tup[2]
            for j in range(len(problem_ids)-1):
                if(j == 0):
                    inputs.append(0)
                    target_instance = [int(problem_ids[j]), int(correctness[j])]
                    targets.append(target_instance)
                    continue

                problem_id = int(problem_ids[j])

                label_index = 0
                if(int(correctness[j]) == 0):
                    label_index = problem_id+1
                else:
                    label_index = problem_id+1 + skills_num
                inputs.append(label_index)
                target_instance = [int(problem_ids[j+1]), int(correctness[j+1])]
                targets.append(target_instance)
            i += 1
    print "Finish reading data"
    return inputs, targets



def main(unused_args):

  #raw_data = reader.ptb_raw_data(FLAGS.data_path)
  #train_data, valid_data, test_data, _ = raw_data
  config = SmallConfig()
  eval_config = SmallConfig()
  eval_config.batch_size = 1
  eval_config.num_steps = 1

  with tf.Graph().as_default(), tf.Session() as session:
    initializer = tf.random_uniform_initializer(-config.init_scale,
                                                config.init_scale)
    with tf.variable_scope("model", reuse=None, initializer=initializer):
      m = StudentModel(is_training=True, config=config)
    with tf.variable_scope("model", reuse=True, initializer=initializer):
      #mvalid = StudentModel(is_training=False, config=config)
      mtest = StudentModel(is_training=False, config=eval_config)

    tf.initialize_all_variables().run()

    for i in range(config.max_max_epoch):
      lr_decay = config.lr_decay ** max(i - config.max_epoch, 0.0)
      m.assign_lr(session, config.learning_rate * lr_decay)

      print("Epoch: %d Learning rate: %.3f" % (i + 1, session.run(m.lr)))
      rmse, auc = run_epoch(session, m, "data/builder_train.csv", m.train_op,
                                   verbose=True)
      print("Epoch: %d Train Perplexity:\n rmse: %.3f \t auc: %.3f" % (i + 1, rmse, auc))
      #valid_perplexity = run_epoch(session, mvalid, valid_data, tf.no_op())
      #print("Epoch: %d Valid Perplexity: %.3f" % (i + 1, valid_perplexity))

      if((i+1) % 5 == 0):
          print("Start to test model....")
          rmse, auc = run_epoch(session, mtest, "data/builder_test.csv", tf.no_op())
          print("Test Perplexity:\n rmse: %.3f \t auc: %.3f" % (rmse, auc))

if __name__ == "__main__":
    tf.app.run()
