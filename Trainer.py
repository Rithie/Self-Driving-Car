import tensorflow as tf
from util import mkdir_tfboard_run_dir,mkdir,shell_command
from data_augmentation import process_data
import os
from Dataset import Dataset
import argparse
from util import mkdir


class Trainer:

    def __init__(self, data_path, model_file, epochs=50, max_sample_records=500, start_epoch=0):
        self.model_file = model_file
        self.data_path = data_path
        self.n_epochs = int(epochs)
        self.max_sample_records = max_sample_records
        self.tfboard_basedir = os.path.join(self.data_path, 'tf_visual_data', 'runs')
        self.tfboard_run_dir = mkdir_tfboard_run_dir(self.tfboard_basedir)
        self.results_file = os.path.join(self.tfboard_run_dir, 'results.txt')
        self.model_checkpoint_dir = os.path.join(self.tfboard_run_dir,'checkpoints')
        self.saver = tf.train.Saver()
        self.start_epoch = start_epoch
        mkdir(self.model_checkpoint_dir)

    # Used to intentionally overfit and check for basic initialization and learning issues
    def train_one_batch(self, sess, x, y_, accuracy, train_step, train_feed_dict, test_feed_dict):

        tf.summary.scalar('accuracy', accuracy)
        merged = tf.summary.merge_all()
        sess.run(tf.global_variables_initializer())
        dataset = Dataset(input_file_path=self.data_path, max_sample_records=self.max_sample_records)

        # Not sure what these two lines do
        run_opts = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
        run_opts_metadata = tf.RunMetadata()

        train_batches = dataset.get_batches(train=True)
        batch = next(train_batches)
        images, labels = process_data(batch)
        train_feed_dict[x] = images
        train_feed_dict[y_] = labels
        for epoch in range(self.n_epochs):
            train_step.run(feed_dict=train_feed_dict)
            train_summary, train_accuracy = sess.run([merged, accuracy], feed_dict=train_feed_dict,
                                                     options=run_opts, run_metadata=run_opts_metadata)
            test_summary, test_accuracy = sess.run([merged, accuracy], feed_dict=train_feed_dict,
                                                   options=run_opts, run_metadata=run_opts_metadata)
            message = "epoch: {0}, training accuracy: {1}, validation accuracy: {2}"
            print(message.format(epoch, train_accuracy, test_accuracy))

    # This function is agnostic to the model
    def train(self, sess, x, y_, accuracy, train_step, train_feed_dict, test_feed_dict):

        # To view graph: tensorboard --logdir=/Users/ryanzotti/Documents/repos/Self_Driving_RC_Car/tf_visual_data/runs
        tf.summary.scalar('accuracy', accuracy)
        merged = tf.summary.merge_all()

        # Archive the model script in case of good results that need to be replicated
        # If model is being restored, then assume model file has already been saved somewhere
        # and that self.model_file is None
        if self.model_file is not None:
            cmd = 'cp {model_file} {archive_path}'
            shell_command(cmd.format(model_file=self.model_file, archive_path=self.tfboard_run_dir + '/'))

        sess.run(tf.global_variables_initializer())

        dataset = Dataset(input_file_path=self.data_path, max_sample_records=self.max_sample_records)

        # TODO: Document and understand what RunOptions does
        run_opts = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
        run_opts_metadata = tf.RunMetadata()

        train_images, train_labels = process_data(dataset.get_sample(train=True))
        train_feed_dict[x] = train_images
        train_feed_dict[y_] = train_labels
        train_summary, train_accuracy = sess.run([merged, accuracy], feed_dict=train_feed_dict,
                                                 options=run_opts, run_metadata=run_opts_metadata)
        test_images, test_labels = process_data(dataset.get_sample(train=False))
        test_feed_dict[x] = test_images
        test_feed_dict[y_] = test_labels
        test_summary, test_accuracy = sess.run([merged, accuracy], feed_dict=test_feed_dict,
                                               options=run_opts, run_metadata=run_opts_metadata)
        message = "epoch: {0}, training accuracy: {1}, validation accuracy: {2}"
        print(message.format(self.start_epoch, train_accuracy, test_accuracy))

        with open(self.results_file,'a') as f:
            f.write(message.format(self.start_epoch, train_accuracy, test_accuracy)+'\n')

        # Save a model checkpoint after every epoch
        self.save_model(sess,epoch=self.start_epoch)

        for epoch in range(self.start_epoch+1, self.start_epoch + self.n_epochs):
            train_batches = dataset.get_batches(train=True)
            for batch in train_batches:
                images, labels = process_data(batch)
                train_feed_dict[x] = images
                train_feed_dict[y_] = labels
                sess.run(train_step,feed_dict=train_feed_dict)

            # TODO: Document and understand what RunOptions does
            run_opts = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
            run_opts_metadata = tf.RunMetadata()

            train_images, train_labels = process_data(dataset.get_sample(train=True))
            train_feed_dict[x] = train_images
            train_feed_dict[y_] = train_labels
            train_summary, train_accuracy = sess.run([merged, accuracy], feed_dict=train_feed_dict,
                                                     options=run_opts, run_metadata=run_opts_metadata)
            test_images, test_labels = process_data(dataset.get_sample(train=False))
            test_feed_dict[x] = test_images
            test_feed_dict[y_] = test_labels
            test_summary, test_accuracy = sess.run([merged, accuracy], feed_dict=test_feed_dict,
                                                   options=run_opts, run_metadata=run_opts_metadata)
            print(message.format(epoch, train_accuracy, test_accuracy))
            with open(self.results_file, 'a') as f:
                f.write(message.format(epoch, train_accuracy, test_accuracy)+'\n')

            # Save a model checkpoint after every epoch
            self.save_model(sess,epoch=epoch)

        # Marks unambiguous successful completion to prevent deletion by cleanup script
        shell_command('touch ' + self.tfboard_run_dir + '/SUCCESS')

    def save_model(self,sess,epoch):
        file_path = os.path.join(self.model_checkpoint_dir,'model')
        self.saver.save(sess,file_path,global_step=epoch)


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("-d", "--datapath", required=False,
                    help="path to all of the data",
                    default='/Users/ryanzotti/Documents/repos/Self_Driving_RC_Car/data')
    ap.add_argument("-e", "--epochs", required=False,
                    help="quantity of batch iterations to run",
                    default='50')
    ap.add_argument("-c", "--checkpointpath", required=False,
                    help="location of checkpoint data",
                    default=None)
    args = vars(ap.parse_args())
    return args
